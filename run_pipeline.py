"""Main pipeline orchestrator — runs all phases end-to-end.

Usage:
    python run_pipeline.py                    # Full pipeline with synthetic data
    python run_pipeline.py --live             # Full pipeline with live scraping
    python run_pipeline.py --phase classify   # Run only classification
    python run_pipeline.py --demo             # Quick demo with 500 reviews
"""

from __future__ import annotations
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings, RAW_DIR, CLEANED_DIR, CLASSIFIED_DIR, REPORTS_DIR
from src.utils import logging as log
from src.utils.llm import get_cost_breakdown


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="SharkNinja Review Intelligence Pipeline")
    parser.add_argument("--live", action="store_true", help="Use live scraping instead of synthetic data")
    parser.add_argument("--phase", choices=["ingest", "clean", "classify", "analyze", "recommend", "all"],
                       default="all", help="Run specific phase")
    parser.add_argument("--demo", action="store_true", help="Quick demo with 500 reviews")
    parser.add_argument("--count", type=int, default=5500, help="Number of synthetic reviews")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM classification (use for testing)")
    parser.add_argument("--consistency-check", action="store_true", help="Run LLM consistency check")
    return parser.parse_args()


async def run_pipeline(args):
    start = time.perf_counter()
    log.section("SharkNinja Review Intelligence Pipeline")
    log.info(f"Mode: {'live' if args.live else 'synthetic'}")
    log.info(f"Phase: {args.phase}")

    reviews = None
    cleaned = None
    classified = None
    analysis_results = None

    # --- Phase 1: Ingestion ---
    if args.phase in ("ingest", "all"):
        log.section("Phase 1: Data Ingestion")

        if args.live:
            from src.ingestion.amazon import scrape_amazon_reviews
            from src.ingestion.reddit import scrape_reddit
            reviews = scrape_amazon_reviews()
            reviews += scrape_reddit()
        else:
            from src.ingestion.synthetic import generate_synthetic_reviews
            count = 500 if args.demo else args.count
            reviews = generate_synthetic_reviews(count=count)

        log.success(f"Ingested {len(reviews)} reviews")

    # --- Phase 2a: Cleaning ---
    if args.phase in ("clean", "all"):
        log.section("Phase 2a: Cleaning")
        from src.cleaning.pipeline import CleaningPipeline

        pipeline = CleaningPipeline()
        cleaned = pipeline.run(reviews)
        log.success(f"Cleaned: {len(cleaned)} reviews retained")

    # --- Phase 2b: Classification ---
    if args.phase in ("classify", "all") and not args.skip_llm:
        log.section("Phase 2b: LLM Classification")

        if cleaned is None:
            from src.utils.schema import RawReview
            path = CLEANED_DIR / "reviews_cleaned.jsonl"
            if path.exists():
                cleaned = []
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            cleaned.append(RawReview.model_validate_json(line))
                log.info(f"Loaded {len(cleaned)} cleaned reviews from disk")
            else:
                log.error("No cleaned reviews found. Run ingestion + cleaning first.")
                return

        from src.classification.classifier import classify_batch, run_consistency_check
        classified = await classify_batch(cleaned)

        if args.consistency_check:
            consistency = await run_consistency_check(cleaned)
            _save_json(consistency, "consistency_check.json")

    # --- Phase 2c: Classification Evaluation ---
    if args.phase in ("classify", "all") and not args.skip_llm:
        if classified is None:
            from src.classification.classifier import load_classified
            classified = load_classified()

        if classified:
            from src.classification.evaluator import ClassificationEvaluator
            evaluator = ClassificationEvaluator(classified)
            eval_results = evaluator.run_all_checks()
            _save_json(eval_results, "eval_results.json")

    # --- Phase 3: Analysis ---
    if args.phase in ("analyze", "all"):
        log.section("Phase 3: Analysis")

        if classified is None:
            from src.classification.classifier import load_classified
            classified = load_classified()

        if not classified:
            log.error("No classified reviews found. Run classification first.")
            return

        from src.analysis.engine import AnalysisEngine
        engine = AnalysisEngine(classified)
        analysis_results = engine.run_all()
        _save_json(analysis_results, "analysis_results.json")

    # --- Phase 4: Recommendations ---
    if args.phase in ("recommend", "all") and not args.skip_llm:
        log.section("Phase 4: Recommendations")

        if analysis_results is None:
            path = REPORTS_DIR / "analysis_results.json"
            if path.exists():
                analysis_results = json.loads(path.read_text(encoding="utf-8"))
            else:
                log.error("No analysis results found. Run analysis first.")
                return

        if classified is None:
            from src.classification.classifier import load_classified
            classified = load_classified()

        from src.recommendations.generator import generate_recommendations
        recs = await generate_recommendations(analysis_results, classified)
        _save_json(recs, "recommendations.json")

        if recs.get("pm_brief"):
            brief_path = REPORTS_DIR / "pm_brief_shark_vacuum.md"
            brief_path.write_text(recs["pm_brief"], encoding="utf-8")
            log.success(f"PM brief saved to {brief_path}")

    # --- Summary ---
    elapsed = time.perf_counter() - start
    log.section("Pipeline Complete")
    log.info(f"Total time: {elapsed:.1f}s")

    cost = get_cost_breakdown()
    if cost["calls"] > 0:
        log.info(f"LLM cost: ${cost['total_usd']:.2f} ({cost['calls']} API calls)")
        log.info(f"Budget remaining: ${settings.llm_budget_usd - cost['total_usd']:.2f}")

    log.success("Dashboard ready: streamlit run src/dashboard/app.py")


def _save_json(data: dict, filename: str):
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    log.info(f"Saved {filename} to {path}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_pipeline(args))
