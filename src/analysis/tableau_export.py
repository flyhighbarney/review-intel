"""Export analysis data to Tableau-compatible formats."""

from __future__ import annotations
import json

import pandas as pd

from config import CLASSIFIED_DIR, REPORTS_DIR
from src.utils.schema import ClassifiedReview
from src.utils import logging as log


def export_for_tableau(reviews: list[ClassifiedReview] | None = None):
    """Export classified reviews and analysis to Excel for Tableau."""

    log.section("Tableau Export")

    if reviews is None:
        from src.classification.classifier import load_classified
        reviews = load_classified()

    if not reviews:
        log.error("No classified reviews to export")
        return

    records = []
    for r in reviews:
        rec = r.model_dump()
        rec["primary_theme"] = rec["primary_theme"].value if hasattr(rec["primary_theme"], "value") else rec["primary_theme"]
        rec["sentiment"] = rec["sentiment"].value if hasattr(rec["sentiment"], "value") else rec["sentiment"]
        rec["source"] = rec["source"].value if hasattr(rec["source"], "value") else rec["source"]
        rec["competitor_mention_count"] = len(rec.get("competitor_mentions", []))
        rec["feature_count"] = len(rec.get("features_mentioned", []))
        rec["is_shark_ninja"] = rec["brand"] in ["Shark", "Ninja"]
        records.append(rec)

    df = pd.DataFrame(records)

    drop_cols = ["competitor_mentions", "features_mentioned", "secondary_themes", "key_phrases"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    out_path = REPORTS_DIR / "tableau_reviews.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Reviews", index=False)

        # Summary pivots
        pivot_brand = df.pivot_table(
            values="review_id", index="brand", columns="sentiment",
            aggfunc="count", fill_value=0
        )
        pivot_brand.to_excel(writer, sheet_name="Brand_Sentiment")

        pivot_theme = df.pivot_table(
            values="review_id", index="primary_theme", columns="category",
            aggfunc="count", fill_value=0
        )
        pivot_theme.to_excel(writer, sheet_name="Theme_Category")

        severity_brand = df.groupby("brand").agg(
            avg_rating=("rating", "mean"),
            avg_severity=("severity", "mean"),
            review_count=("review_id", "count"),
            neg_pct=("sentiment", lambda x: (x == "negative").mean()),
        ).round(3)
        severity_brand.to_excel(writer, sheet_name="Brand_Scorecard")

    log.success(f"Tableau export saved to {out_path}")

    analysis_path = REPORTS_DIR / "analysis_results.json"
    if analysis_path.exists():
        results = json.loads(analysis_path.read_text(encoding="utf-8"))
        comps = results.get("competitor_comparison", [])
        if comps:
            comp_df = pd.DataFrame(comps)
            comp_path = REPORTS_DIR / "tableau_competitor_comparison.xlsx"
            comp_df.to_excel(comp_path, index=False)
            log.success(f"Competitor comparison export: {comp_path}")

    return out_path


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    export_for_tableau()
