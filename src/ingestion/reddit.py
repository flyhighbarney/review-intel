"""Reddit review/opinion ingestion via PRAW."""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone

import praw

from config import settings, RAW_DIR
from src.utils.schema import RawReview, Source
from src.utils import logging as log


SUBREDDITS = {
    "vacuums": ["VacuumCleaners", "CleaningTips", "homeautomation"],
    "blenders": ["Blenders", "Cooking", "MealPrepSunday"],
    "air_fryers": ["airfryer", "Cooking", "EatCheapAndHealthy"],
    "coffee_makers": ["Coffee", "espresso", "coffeemachines"],
}

BRAND_KEYWORDS = {
    "Shark": ["shark", "shark vacuum", "shark navigator", "shark stratos"],
    "Ninja": ["ninja blender", "ninja foodi", "ninja air fryer", "ninja dualbrew", "ninja creami"],
    "Dyson": ["dyson", "dyson v15", "dyson v12"],
    "iRobot": ["irobot", "roomba"],
    "Bissell": ["bissell", "crosswave"],
    "Vitamix": ["vitamix"],
    "Nutribullet": ["nutribullet"],
    "Cosori": ["cosori"],
    "Breville": ["breville"],
    "Keurig": ["keurig", "k-cup"],
    "Instant Pot": ["instant pot", "instant vortex"],
}


def scrape_reddit(
    category: str | None = None,
    max_posts: int = 500,
    max_comments_per_post: int = 20,
) -> list[RawReview]:
    if not settings.reddit_client_id:
        log.warn("No Reddit credentials — set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")
        return []

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    reviews: list[RawReview] = []
    categories = [category] if category else list(SUBREDDITS.keys())

    for cat in categories:
        subs = SUBREDDITS.get(cat, [])
        for sub_name in subs:
            log.info(f"Scanning r/{sub_name} for {cat} reviews...")
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.search(
                    _build_query(cat), sort="relevance", time_filter="year", limit=max_posts
                ):
                    brand = _detect_brand(post.title + " " + (post.selftext or ""))
                    if not brand:
                        continue

                    if len(post.selftext or "") > 50:
                        reviews.append(_post_to_review(post, cat, brand))

                    post.comments.replace_more(limit=0)
                    for comment in post.comments[:max_comments_per_post]:
                        if len(comment.body) > 50:
                            c_brand = _detect_brand(comment.body) or brand
                            reviews.append(_comment_to_review(comment, post, cat, c_brand))

            except Exception as e:
                log.error(f"Error in r/{sub_name}: {e}")

    _save_raw(reviews, "reddit")
    log.success(f"Collected {len(reviews)} Reddit reviews across {len(categories)} categories")
    return reviews


def _build_query(category: str) -> str:
    queries = {
        "vacuums": "vacuum cleaner review OR recommend OR best OR worst",
        "blenders": "blender review OR recommend OR best OR worst",
        "air_fryers": "air fryer review OR recommend OR best OR worst",
        "coffee_makers": "coffee maker OR espresso machine review OR recommend",
    }
    return queries.get(category, f"{category} review")


def _detect_brand(text: str) -> str | None:
    text_lower = text.lower()
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return brand
    return None


def _post_to_review(post, category: str, brand: str) -> RawReview:
    return RawReview(
        review_id=f"reddit_{post.id}",
        product_id=f"reddit_{brand.lower()}_{category}",
        product_name=f"{brand} (Reddit mention)",
        brand=brand,
        category=category,
        rating=_estimate_rating_from_sentiment(post.selftext),
        title=post.title,
        review_text=post.selftext[:3000],
        date=datetime.fromtimestamp(post.created_utc, tz=timezone.utc).date(),
        verified_purchase=False,
        helpful_votes=post.score,
        source=Source.REDDIT,
        reviewer_name=str(post.author) if post.author else "",
        source_url=f"https://reddit.com{post.permalink}",
    )


def _comment_to_review(comment, post, category: str, brand: str) -> RawReview:
    rid = hashlib.md5(comment.id.encode()).hexdigest()[:12]
    return RawReview(
        review_id=f"reddit_c_{rid}",
        product_id=f"reddit_{brand.lower()}_{category}",
        product_name=f"{brand} (Reddit mention)",
        brand=brand,
        category=category,
        rating=_estimate_rating_from_sentiment(comment.body),
        title=post.title[:100],
        review_text=comment.body[:3000],
        date=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).date(),
        verified_purchase=False,
        helpful_votes=comment.score,
        source=Source.REDDIT,
        reviewer_name=str(comment.author) if comment.author else "",
        source_url=f"https://reddit.com{comment.permalink}",
    )


def _estimate_rating_from_sentiment(text: str) -> float:
    """Rough heuristic rating — will be overridden by LLM classification."""
    positive = sum(1 for w in ["love", "great", "best", "amazing", "excellent", "recommend"] if w in text.lower())
    negative = sum(1 for w in ["hate", "worst", "terrible", "broke", "returned", "avoid", "waste"] if w in text.lower())
    if positive > negative:
        return 4.0
    elif negative > positive:
        return 2.0
    return 3.0


def _save_raw(reviews: list[RawReview], tag: str):
    if not reviews:
        return
    out = RAW_DIR / f"{tag}_reviews.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(r.model_dump_json() + "\n")
