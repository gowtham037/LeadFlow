# ============================================================
# Lead Intelligence Platform — developer commands
# ============================================================
SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help up down restart logs db-shell db-init reset psql

help:
	@echo "Lead Intelligence Platform — make targets"
	@echo "  make up         Start Postgres in background"
	@echo "  make down       Stop containers (keeps volume)"
	@echo "  make restart    Restart containers"
	@echo "  make logs       Tail Postgres logs"
	@echo "  make db-shell   Open psql inside container"
	@echo "  make db-init    Apply database/schema/*.sql in order"
	@echo "  make psql       Alias for db-shell"
	@echo "  make reset      DESTROY volume + containers, then up"
	@echo "  make health     Check Postgres readiness"

up:
	@cp -n .env.example .env || true
	$(COMPOSE) up -d
	@echo "Waiting for Postgres to be healthy..."
	@until docker inspect --format='{{.State.Health.Status}}' lip-postgres 2>/dev/null | grep -q healthy; do \
		sleep 1; printf '.'; \
	done; echo " OK"

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f db

db-shell:
	$(COMPOSE) exec db psql -U leadflow -d leadflow

psql: db-shell

db-init:
	@echo "Applying database/schema/*.sql in lexical order..."
	@for f in database/schema/*.sql; do \
		echo "  -> $$f"; \
		docker exec -i lip-postgres psql -U leadflow -d leadflow -v ON_ERROR_STOP=1 < "$$f" || exit 1; \
	done
	@echo "Schema applied."

health:
	@docker inspect --format='{{.State.Health.Status}}' lip-postgres || echo "container not running"

reset:
	@echo "This will DELETE the database volume. Ctrl+C to cancel."
	@sleep 3
	$(COMPOSE) down -v
	$(MAKE) up
