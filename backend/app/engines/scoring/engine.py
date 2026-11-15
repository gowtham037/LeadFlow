"""
Deterministic scoring engine.

score(features, rule) → ScoreResult

Rules for reproducibility:
  - Every feature maps to a fixed points table (no randomness)
  - Component scores are clamped to component max (their weight)
  - Total = sum of components (bounded 0..100)
  - Same features + same rule = same result

Explainability:
  Every contribution includes raw value, points, and human-readable explanation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from backend.app.engines.scoring.features import Features
from backend.app.models.enums import ScoreCategory


@dataclass
class Contribution:
    feature: str
    raw_value: int | float | str | bool
    points: int
    weight_max: int
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    total: int
    category: ScoreCategory
    fit_score: int
    intent_score: int
    engagement_score: int
    recency_score: int
    rule_version: str
    input_cutoff_at: datetime
    contributions: list[Contribution] = field(default_factory=list)

    def contributions_as_dicts(self) -> list[dict]:
        return [c.to_dict() for c in self.contributions]


class ScoreRuleLike:
    """Minimal interface — matches ScoreRule ORM attributes we actually use."""
    version: str
    fit_weight: int
    intent_weight: int
    engagement_weight: int
    recency_weight: int
    hot_threshold: int
    warm_threshold: int
    nurture_threshold: int


# ---------- Fit sub-scorer (max = fit_weight, default 30) ----------
def _score_fit(f: Features, max_points: int) -> tuple[int, list[Contribution]]:
    # 4 sub-features, each contributes proportionally
    # Employee count: tier bands
    if f.employee_count >= 1000:
        emp_pts = 10
        emp_label = "Enterprise (>1k employees)"
    elif f.employee_count >= 200:
        emp_pts = 7
        emp_label = "Mid-market (200-999 employees)"
    elif f.employee_count >= 50:
        emp_pts = 4
        emp_label = "SMB (50-199 employees)"
    else:
        emp_pts = 1
        emp_label = "Small (<50 employees)"

    # Industry match: target industries
    target_industries = {"Software as a Service", "Financial Technology", "Healthcare"}
    industry_pts = 8 if f.industry in target_industries else 3
    industry_label = f"{f.industry} ({'target' if industry_pts == 8 else 'non-target'})"

    # Revenue band
    if f.annual_revenue_usd >= 50_000_000:
        rev_pts = 8
        rev_label = ">$50M revenue"
    elif f.annual_revenue_usd >= 5_000_000:
        rev_pts = 5
        rev_label = "$5M–$50M revenue"
    elif f.annual_revenue_usd >= 1_000_000:
        rev_pts = 3
        rev_label = "$1M–$5M revenue"
    else:
        rev_pts = 1
        rev_label = "<$1M revenue"

    # Territory match
    territory_pts = 4 if f.territory_match else 0
    territory_label = "matches company territory" if f.territory_match else "outside company territory"

    # Sum sub-points (out of 30 possible here) → scale to max_points
    raw_total = emp_pts + industry_pts + rev_pts + territory_pts
    scale = max_points / 30.0
    score = min(max_points, int(round(raw_total * scale)))

    contributions = [
        Contribution("fit.employee_count", f.employee_count, emp_pts, 10, emp_label),
        Contribution("fit.industry", f.industry, industry_pts, 8, industry_label),
        Contribution("fit.annual_revenue_usd", f.annual_revenue_usd, rev_pts, 8, rev_label),
        Contribution("fit.territory_match", f.territory_match, territory_pts, 4, territory_label),
    ]
    return score, contributions


# ---------- Intent sub-scorer (max = intent_weight, default 35) ----------
def _score_intent(f: Features, max_points: int) -> tuple[int, list[Contribution]]:
    # Intent rewards ACCUMULATION of high-signal activities.
    # Demo > meeting > content > call. Signals above ~3 don't add more points
    # (a lead with 5 demos isn't 5x more valuable than one with 1).
    # Targets: 35 points when a lead has 2-3 demos, 1-2 meetings, some content.
    demo_pts = min(18, f.demo_requests * 9)          # 2 demos → 18
    meeting_pts = min(8, f.meetings * 4)             # 2 meetings → 8
    content_pts = min(5, f.content_downloads * 2)    # 3 downloads → 5
    call_pts = min(4, f.calls * 2)                   # 2 calls → 4

    raw_total = demo_pts + meeting_pts + content_pts + call_pts  # max 35
    scale = max_points / 35.0
    score = min(max_points, int(round(raw_total * scale)))

    contributions = [
        Contribution("intent.demo_requests", f.demo_requests, demo_pts, 18,
                     f"{f.demo_requests} demo request(s)"),
        Contribution("intent.meetings", f.meetings, meeting_pts, 8,
                     f"{f.meetings} meeting(s)"),
        Contribution("intent.content_downloads", f.content_downloads, content_pts, 5,
                     f"{f.content_downloads} content download(s)"),
        Contribution("intent.calls", f.calls, call_pts, 4,
                     f"{f.calls} call(s)"),
    ]
    return score, contributions


# ---------- Engagement sub-scorer (max = engagement_weight, default 25) ----------
def _score_engagement(f: Features, max_points: int) -> tuple[int, list[Contribution]]:
    opens_pts = min(8, f.email_opens * 2)
    clicks_pts = min(10, f.email_clicks * 5)
    visits_pts = min(7, f.web_visits * 2)

    raw_total = opens_pts + clicks_pts + visits_pts  # max 25
    scale = max_points / 25.0
    score = min(max_points, int(round(raw_total * scale)))

    contributions = [
        Contribution("engagement.email_opens", f.email_opens, opens_pts, 8,
                     f"{f.email_opens} email open(s)"),
        Contribution("engagement.email_clicks", f.email_clicks, clicks_pts, 10,
                     f"{f.email_clicks} email click(s)"),
        Contribution("engagement.web_visits", f.web_visits, visits_pts, 7,
                     f"{f.web_visits} web visit(s)"),
    ]
    return score, contributions


# ---------- Recency sub-scorer (max = recency_weight, default 10) ----------
def _score_recency(f: Features, max_points: int) -> tuple[int, list[Contribution]]:
    days = f.days_since_last_activity
    if days <= 3:
        pts, label = 10, f"last activity {days}d ago (very fresh)"
    elif days <= 7:
        pts, label = 8, f"last activity {days}d ago (fresh)"
    elif days <= 14:
        pts, label = 5, f"last activity {days}d ago (warm)"
    elif days <= 30:
        pts, label = 3, f"last activity {days}d ago (stale)"
    elif days <= 90:
        pts, label = 1, f"last activity {days}d ago (cold)"
    else:
        pts, label = 0, "no recent activity (>90d or none)"

    scale = max_points / 10.0
    score = min(max_points, int(round(pts * scale)))
    contributions = [
        Contribution("recency.days_since_last_activity", days, pts, 10, label),
    ]
    return score, contributions


# ---------- Category classifier ----------
def _categorize(total: int, rule: ScoreRuleLike) -> ScoreCategory:
    if total >= rule.hot_threshold:
        return ScoreCategory.HOT
    if total >= rule.warm_threshold:
        return ScoreCategory.WARM
    if total >= rule.nurture_threshold:
        return ScoreCategory.NURTURE
    return ScoreCategory.COLD


# ---------- Public entry point ----------
def calculate_score(features: Features, rule: ScoreRuleLike) -> ScoreResult:
    """
    Deterministic score for the given features under the given rule.

    Guarantees:
      - Same (features, rule) → identical output every call
      - Sum of component scores == total (bounded 0..100)
      - Contributions list has one entry per sub-feature
    """
    fit_score, fit_contribs = _score_fit(features, rule.fit_weight)
    intent_score, intent_contribs = _score_intent(features, rule.intent_weight)
    engagement_score, engagement_contribs = _score_engagement(features, rule.engagement_weight)
    recency_score, recency_contribs = _score_recency(features, rule.recency_weight)

    total = fit_score + intent_score + engagement_score + recency_score
    # Final clamp (defensive)
    total = max(0, min(100, total))

    category = _categorize(total, rule)

    return ScoreResult(
        total=total,
        category=category,
        fit_score=fit_score,
        intent_score=intent_score,
        engagement_score=engagement_score,
        recency_score=recency_score,
        rule_version=rule.version,
        input_cutoff_at=features.cutoff_at,  # type: ignore[arg-type]
        contributions=(
            fit_contribs + intent_contribs + engagement_contribs + recency_contribs
        ),
    )

