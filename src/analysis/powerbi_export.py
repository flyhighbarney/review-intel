"""Export analysis data to Power BI-ready tables (star schema + pre-aggregates).

Additive to the existing Streamlit dashboard and Tableau export — this module does
not modify either. It reuses AnalysisEngine's calculations verbatim so the numbers
in Power BI match exactly what engine.py computes.

Outputs (written to reports/powerbi/):
    fact_reviews.csv              — one row per classified review (fact grain)
    dim_date.csv                  — date dimension (contiguous calendar)
    dim_brand.csv                 — brand dimension (+ Shark/Ninja flag)
    dim_category.csv              — category dimension
    agg_top_issues.csv            — mirrors engine.top_issues_by_category()
    agg_competitor_comparison.csv — mirrors engine.competitor_comparison()
    agg_emerging_issues.csv       — mirrors engine.emerging_issues(days=90)
    powerbi_model.xlsx            — all of the above as one multi-sheet workbook

Star schema: fact_reviews joins to dim_brand (brand), dim_category (category),
and dim_date (review_date) on their natural keys.
"""

from __future__ import annotations

import pandas as pd

from config import REPORTS_DIR, settings
from src.analysis.engine import AnalysisEngine
from src.utils.schema import ClassifiedReview
from src.utils import logging as log

POWERBI_DIR = REPORTS_DIR / "powerbi"

SHARK_NINJA = set(settings.shark_ninja_brands)


def _enum_value(v):
    """Unwrap an Enum to its .value; pass through plain values/None."""
    return v.value if hasattr(v, "value") else v


# ─── Fact table ──────────────────────────────────────────────────────────────

def build_fact_reviews(reviews: list[ClassifiedReview]) -> pd.DataFrame:
    """One row per classified review — the fact grain of the star schema."""
    records = []
    for r in reviews:
        rec = r.model_dump()

        # Normalize enums to their string values.
        rec["primary_theme"] = _enum_value(rec["primary_theme"])
        rec["sentiment"] = _enum_value(rec["sentiment"])
        rec["source"] = _enum_value(rec["source"])
        rec["secondary_themes"] = ", ".join(_enum_value(t) for t in rec.get("secondary_themes", []))

        # Flatten competitor_mentions (list of {"brand","context"}) into scalars.
        mentions = rec.get("competitor_mentions", [])
        rec["competitor_mention_count"] = len(mentions)
        rec["competitor_brands_mentioned"] = ", ".join(
            sorted({m.get("brand", "") for m in mentions if m.get("brand")})
        )
        rec["favorable_competitor_mentions"] = sum(
            1 for m in mentions if m.get("context") == "favorable"
        )

        # Flatten remaining list fields to keep the fact table tabular.
        rec["features_mentioned"] = ", ".join(rec.get("features_mentioned", []))
        rec["feature_count"] = len(r.features_mentioned)
        rec["key_phrases"] = ", ".join(rec.get("key_phrases", []))

        # Derived flags / helper columns for Power BI.
        rec["is_shark_ninja"] = rec["brand"] in SHARK_NINJA
        rec["is_negative"] = rec["sentiment"] == "negative"
        rec["is_positive"] = rec["sentiment"] == "positive"
        # review_date is the foreign key into dim_date (kept as a clean date type).
        rec["review_date"] = rec.get("date")

        records.append(rec)

    df = pd.DataFrame(records)

    # Drop the raw nested column (flattened above) and the original `date`
    # (superseded by `review_date`, the clean FK into dim_date).
    df = df.drop(columns=[c for c in ["competitor_mentions", "date"] if c in df.columns])

    if "review_date" in df.columns:
        df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce").dt.date

    return df


# ─── Dimensions ──────────────────────────────────────────────────────────────

def build_dim_brand(fact: pd.DataFrame) -> pd.DataFrame:
    """Brand dimension. Natural key = brand."""
    # Map each brand to the category it competes in (for the competitor label).
    comp_lookup = {}
    for cat, brands in settings.competitor_brands.items():
        for b in brands:
            comp_lookup.setdefault(b, cat)

    brands = sorted(fact["brand"].unique())
    rows = []
    for b in brands:
        is_ours = b in SHARK_NINJA
        rows.append({
            "brand": b,
            "is_shark_ninja": is_ours,
            "brand_type": "Shark/Ninja" if is_ours else "Competitor",
        })
    return pd.DataFrame(rows)


def build_dim_category(fact: pd.DataFrame) -> pd.DataFrame:
    """Category dimension. Natural key = category."""
    cats = sorted(fact["category"].unique())
    rows = [{
        "category": c,
        "category_label": c.replace("_", " ").title(),
    } for c in cats]
    return pd.DataFrame(rows)


def build_dim_date(fact: pd.DataFrame) -> pd.DataFrame:
    """Contiguous calendar dimension spanning the review dates.

    Natural key = date. Contiguous so Power BI time-intelligence works cleanly.
    """
    dates = pd.to_datetime(fact["review_date"], errors="coerce").dropna()
    if dates.empty:
        return pd.DataFrame(columns=[
            "date", "year", "quarter", "month_num", "month_name",
            "month_year", "year_month_sort", "day",
        ])

    start = dates.min().normalize()
    end = dates.max().normalize()
    cal = pd.date_range(start=start, end=end, freq="D")

    df = pd.DataFrame({"date": cal})
    df["year"] = df["date"].dt.year
    df["quarter"] = "Q" + df["date"].dt.quarter.astype(str)
    df["month_num"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.strftime("%b")
    df["month_year"] = df["date"].dt.strftime("%b %Y")
    # Integer sort key so "Jan 2025" sorts before "Feb 2025" on a Power BI axis.
    df["year_month_sort"] = df["date"].dt.year * 100 + df["date"].dt.month
    df["day"] = df["date"].dt.day
    df["date"] = df["date"].dt.date
    return df


# ─── Pre-aggregated tables (mirror engine.py exactly) ────────────────────────

def build_agg_top_issues(results: dict) -> pd.DataFrame:
    """Flatten engine.top_issues_by_category() {category: [issues]} into rows."""
    rows = []
    for category, issues in results.get("top_issues", {}).items():
        for rank, issue in enumerate(issues, start=1):
            rows.append({
                "category": category,
                "rank": rank,
                "brand": issue["brand"],
                "theme": issue["theme"],
                "frequency": issue["frequency"],
                "avg_severity": issue["avg_severity"],
                "recency_weight": issue["recency_weight"],
                "impact_score": issue["impact_score"],
                "top_failure_mode": issue.get("top_failure_mode"),
                "affected_products": ", ".join(issue.get("affected_products", [])),
                "sample_quote": (issue.get("sample_quotes") or [""])[0][:500],
            })
    return pd.DataFrame(rows)


def build_agg_competitor_comparison(results: dict) -> pd.DataFrame:
    """engine.competitor_comparison() is already a flat list of dicts."""
    return pd.DataFrame(results.get("competitor_comparison", []))


def build_agg_emerging_issues(results: dict) -> pd.DataFrame:
    """engine.emerging_issues(days=90) is already a flat list of dicts."""
    return pd.DataFrame(results.get("emerging_issues", []))


# ─── Orchestration ───────────────────────────────────────────────────────────

def export_for_powerbi(reviews: list[ClassifiedReview] | None = None) -> Path:
    """Build all Power BI tables and write CSVs + one multi-sheet workbook."""
    log.section("Power BI Export")

    if reviews is None:
        from src.classification.classifier import load_classified
        reviews = load_classified()

    if not reviews:
        log.error("No classified reviews to export")
        return None

    # Reuse engine.py's calculations verbatim so numbers match the Streamlit app.
    engine = AnalysisEngine(reviews)
    results = engine.run_all()

    tables = {
        "fact_reviews": build_fact_reviews(reviews),
    }
    fact = tables["fact_reviews"]
    tables["dim_date"] = build_dim_date(fact)
    tables["dim_brand"] = build_dim_brand(fact)
    tables["dim_category"] = build_dim_category(fact)
    tables["agg_top_issues"] = build_agg_top_issues(results)
    tables["agg_competitor_comparison"] = build_agg_competitor_comparison(results)
    tables["agg_emerging_issues"] = build_agg_emerging_issues(results)

    POWERBI_DIR.mkdir(parents=True, exist_ok=True)

    # One CSV per table — cleanest for importing as separate Power BI queries.
    for name, df in tables.items():
        path = POWERBI_DIR / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        log.info(f"{name}: {len(df):,} rows -> {path.name}")

    # Also a single workbook for convenience (mirrors tableau_export.py style).
    xlsx_path = POWERBI_DIR / "powerbi_model.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            # Excel sheet names cap at 31 chars.
            df.to_excel(writer, sheet_name=name[:31], index=False)

    log.success(f"Power BI export saved to {POWERBI_DIR}")
    return xlsx_path


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    export_for_powerbi()
