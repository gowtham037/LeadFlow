#!/usr/bin/env bash
# ============================================================
# LeadFlow — single local orchestrator
#
# Usage:
#   ./run-local.sh                 boot FastAPI (default: port 8002)
#   ./run-local.sh 8003            boot FastAPI on custom port
#   ./run-local.sh seed            seed DB (starter mode, seed 20261022)
#   ./run-local.sh seed full       seed DB (full mode, seed 20261022)
#   ./run-local.sh seed full 42    seed DB (full mode, custom seed)
#   ./run-local.sh check           verify DB state
#   ./run-local.sh help            show this help
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

HOST="0.0.0.0"
CMD="${1:-serve}"

# ---------- helpers ----------
activate_venv() {
  if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f ".venv/bin/activate" ]]; then
      echo "[run-local] activating .venv"
      # shellcheck disable=SC1091
      source .venv/bin/activate
    else
      echo "[run-local] ERROR: .venv not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
      exit 1
    fi
  fi
}

ensure_env() {
  if [[ ! -f ".env" ]]; then
    echo "[run-local] .env missing — copying from .env.example"
    cp .env.example .env
  fi
}

ensure_postgres() {
  echo "[run-local] checking Postgres container..."
  if ! docker ps --filter name=lip-postgres --filter status=running --format '{{.Names}}' | grep -q lip-postgres; then
    echo "[run-local] ERROR: lip-postgres container not running. Start with: make up"
    exit 1
  fi
  local health
  health=$(docker inspect --format='{{.State.Health.Status}}' lip-postgres 2>/dev/null || echo "unknown")
  if [[ "$health" != "healthy" ]]; then
    echo "[run-local] waiting for Postgres to be healthy (current: $health)..."
    for _ in $(seq 1 30); do
      health=$(docker inspect --format='{{.State.Health.Status}}' lip-postgres 2>/dev/null || echo "unknown")
      [[ "$health" == "healthy" ]] && break
      sleep 1
    done
    if [[ "$health" != "healthy" ]]; then
      echo "[run-local] ERROR: Postgres did not become healthy in 30s"
      exit 1
    fi
  fi
  echo "[run-local] Postgres healthy."
}

show_db_target() {
  PYTHONPATH=. python3 -c "from backend.app.config import settings; print('[run-local] DB URL:', settings.database_url.split('@')[-1])"
}

# ---------- commands ----------

cmd_serve() {
  local port="${1:-8002}"
  activate_venv
  ensure_env
  ensure_postgres
  show_db_target
  echo "[run-local] starting uvicorn on http://${HOST}:${port}"
  echo "[run-local] docs:   http://localhost:${port}/docs"
  echo "[run-local] health: http://localhost:${port}/health"
  echo "[run-local] Ctrl+C to stop"
  echo ""
  PYTHONPATH=. exec uvicorn backend.app.main:app --host "$HOST" --port "$port"
}

cmd_seed() {
  local mode="${1:-starter}"
  local seed="${2:-20261022}"
  activate_venv
  ensure_env
  ensure_postgres
  show_db_target
  echo ""
  echo "[run-local] running generator: --mode ${mode} --seed ${seed}"
  echo ""
  PYTHONPATH=. python -m backend.app.data_generator --mode "$mode" --seed "$seed"
}

cmd_check() {
  echo "=================================================="
  echo "LeadFlow DB State Check"
  echo "=================================================="

  echo ""
  echo "--- Row counts per table ---"
  docker exec lip-postgres psql -U leadflow -d leadflow -c "
  SELECT
    (SELECT count(*) FROM roles)                   AS roles,
    (SELECT count(*) FROM territories)             AS territories,
    (SELECT count(*) FROM products)                AS products,
    (SELECT count(*) FROM sales_reps)              AS sales_reps,
    (SELECT count(*) FROM campaigns)               AS campaigns,
    (SELECT count(*) FROM companies)               AS companies,
    (SELECT count(*) FROM contacts)                AS contacts,
    (SELECT count(*) FROM leads)                   AS leads,
    (SELECT count(*) FROM lead_campaigns)          AS lead_campaigns,
    (SELECT count(*) FROM activities)              AS activities,
    (SELECT count(*) FROM consents)                AS consents,
    (SELECT count(*) FROM score_rules)             AS score_rules,
    (SELECT count(*) FROM lead_score_history)      AS score_history,
    (SELECT count(*) FROM lead_assignment_history) AS assignment_history,
    (SELECT count(*) FROM tasks)                   AS tasks,
    (SELECT count(*) FROM opportunities)           AS opportunities,
    (SELECT count(*) FROM stage_history)           AS stage_history,
    (SELECT count(*) FROM duplicate_groups)        AS duplicate_groups,
    (SELECT count(*) FROM exception_records)       AS exceptions,
    (SELECT count(*) FROM audit_log)               AS audit_log;
  "

  echo ""
  echo "--- Score category distribution ---"
  docker exec lip-postgres psql -U leadflow -d leadflow -c "
  SELECT current_score_category, count(*) AS leads
  FROM leads
  GROUP BY current_score_category
  ORDER BY current_score_category;"

  echo ""
  echo "--- Lead status distribution ---"
  docker exec lip-postgres psql -U leadflow -d leadflow -c "
  SELECT status, count(*) AS leads
  FROM leads
  GROUP BY status
  ORDER BY status;"

  echo ""
  echo "--- 5 anomaly types ---"
  docker exec lip-postgres psql -U leadflow -d leadflow -c "
  SELECT issue_type, severity, count(*) AS n
  FROM exception_records
  GROUP BY issue_type, severity
  ORDER BY issue_type;"

  echo ""
  echo "--- Ground truth CSV ---"
  if [[ -f data/ground_truth/ground_truth.csv ]]; then
    cat data/ground_truth/ground_truth.csv
    echo ""
    echo "--- SHA-256 ---"
    sha256sum data/ground_truth/ground_truth.csv
  else
    echo "ground_truth.csv NOT FOUND"
  fi

  echo ""
  echo "=================================================="
  echo "Done."
  echo "=================================================="
}

cmd_help() {
  echo "LeadFlow — local orchestrator"
  echo ""
  echo "  ./run-local.sh                 boot FastAPI (default: port 8002)"
  echo "  ./run-local.sh 8003            boot FastAPI on custom port"
  echo "  ./run-local.sh seed            seed DB (starter mode)"
  echo "  ./run-local.sh seed full       seed DB (full mode)"
  echo "  ./run-local.sh seed full 42    seed DB (custom seed)"
  echo "  ./run-local.sh check           verify DB state"
  echo "  ./run-local.sh help            show this help"
}

# ---------- dispatch ----------
case "$CMD" in
  serve|"")
    cmd_serve "${2:-8002}"
    ;;
  seed)
    cmd_seed "${2:-starter}" "${3:-20261022}"
    ;;
  check)
    cmd_check
    ;;
  help|-h|--help)
    cmd_help
    ;;
  *)
    # If it looks like a port number, treat as serve with custom port
    if [[ "$CMD" =~ ^[0-9]+$ ]]; then
      cmd_serve "$CMD"
    else
      echo "[run-local] unknown command: $CMD"
      cmd_help
      exit 1
    fi
    ;;
esac