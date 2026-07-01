"""Amazon review ingestion via Apify's product review scraper."""

from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from apify_client import ApifyClient

from config import settings, RAW_DIR, PRODUCT_CATALOG
from src.utils.schema import RawReview, Source
from src.utils import logging as log


APIFY_ACTOR = "junglee/amazon-reviews-scraper"


def scrape_amazon_reviews(
    category: str | None = None,
    max_per_product: int = 200,
    dry_run: bool = False,
) -> list[RawReview]:
    """Scrape Amazon reviews using Apify. Returns list of RawReview objects."""

    if not settings.apify_api_token:
        log.warn("No Apify token set — use generate_synthetic or provide APIFY_API_TOKEN in .env")
        return []

    client = ApifyClient(settings.apify_api_token)
    all_reviews: list[RawReview] = []

    categories = [category] if category else list(PRODUCT_CATALOG.keys())

    for cat in categories:
        brands = PRODUCT_CATALOG.get(cat, {})
        for brand, products in brands.items():
            for product in products:
                asin = product["asin"]
                name = product["name"]
                log.info(f"Scraping {name} ({asin})...")

                if dry_run:
                    log.info(f"  [DRY RUN] Would scrape {asin}")
                    continue

                run_input = {
                    "productUrls": [{"url": f"https://www.amazon.com/dp/{asin}"}],
                    "maxReviews": max_per_product,
                    "sort": "recent",
                }

                try:
                    run = client.actor(APIFY_ACTOR).call(run_input=run_input)
                    dataset = client.dataset(run["defaultDatasetId"])

                    for item in dataset.iterate_items():
                        review = RawReview(
                            review_id=f"amz_{asin}_{item.get('id', '')}",
                            product_id=asin,
                            product_name=name,
                            brand=brand,
                            category=cat,
                            rating=float(item.get("rating", 0)),
                            title=item.get("title", ""),
                            review_text=item.get("text", item.get("review", "")),
                            date=_parse_date(item.get("date")),
                            verified_purchase=item.get("isVerified", False),
                            helpful_votes=item.get("helpfulVotes", 0),
                            source=Source.AMAZON,
                            reviewer_name=item.get("userName", ""),
                            source_url=item.get("url", f"https://amazon.com/dp/{asin}"),
                        )
                        all_reviews.append(review)

                    log.success(f"  Got {len(all_reviews)} reviews for {name}")
                except Exception as e:
                    log.error(f"  Failed to scrape {name}: {e}")

    _save_raw(all_reviews, "amazon")
    return all_reviews


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _save_raw(reviews: list[RawReview], tag: str):
    if not reviews:
        return
    out = RAW_DIR / f"{tag}_reviews.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(r.model_dump_json() + "\n")
    log.success(f"Saved {len(reviews)} reviews to {out}")
