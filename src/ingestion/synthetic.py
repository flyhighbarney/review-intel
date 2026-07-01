"""Generate realistic synthetic review data for development and demos.

Produces 5,000+ reviews that mirror real distribution patterns:
- Rating distribution follows Amazon's J-curve (more 5s and 1s than 3s)
- Theme distribution matches observed patterns per category
- Includes realistic failure modes, timeline language, and competitor mentions
"""

from __future__ import annotations
import hashlib
import random
from datetime import date, timedelta

from config import PRODUCT_CATALOG, RAW_DIR
from src.utils.schema import RawReview, Source
from src.utils import logging as log


REVIEW_TEMPLATES = {
    "vacuums": {
        "positive": {
            "power": [
                "Incredible suction power. Picks up pet hair from deep carpet like nothing else. {brand} really nailed it.",
                "The suction on this {product} is unreal. My floors have never been cleaner. Worth every penny.",
                "After trying {competitor}, I switched to {brand} and the suction difference is night and day.",
            ],
            "usability": [
                "So easy to maneuver around furniture. The swivel head makes it a joy to use. Lightweight too.",
                "Love how easy this is to empty the dust cup. No mess, no fuss. Great design by {brand}.",
                "The {product} is surprisingly lightweight for how powerful it is. My back thanks me.",
            ],
            "noise": [
                "Much quieter than my old {competitor}. Can vacuum while the baby naps now.",
                "I was amazed at how quiet this runs. My previous vacuum woke up the entire house.",
            ],
            "battery": [
                "Battery lasts a solid 40+ minutes on normal mode. More than enough for my 2000 sq ft home.",
                "Fast charging and long battery life. {brand} got the cordless formula right.",
            ],
        },
        "negative": {
            "durability": [
                "Stopped working after {months} months. The motor just died. Very disappointed for the price.",
                "The roller brush broke after {months} months of normal use. Cheap plastic parts inside.",
                "Suction dropped dramatically after {months} months. Filters clog quickly and replacements are expensive.",
                "Handle cracked at the joint after just {months} months. Build quality is not what I expected from {brand}.",
            ],
            "noise": [
                "This thing is LOUD. Like jet engine loud. Can't use it when anyone is sleeping or on a call.",
                "The noise level is unbearable. My {competitor} was much quieter for similar suction.",
            ],
            "usability": [
                "The dust cup is tiny and needs emptying every 5 minutes. Very frustrating for larger homes.",
                "Gets stuck on every rug edge. The navigation is terrible compared to my old {competitor}.",
                "Way too heavy to carry up stairs. Marketed as portable but my arms are dead after one floor.",
            ],
            "cleaning": [
                "The filter is nearly impossible to clean properly. Water gets trapped inside.",
                "Hair wraps around the brush roll constantly. Have to cut it out with scissors every use.",
            ],
        },
    },
    "blenders": {
        "positive": {
            "power": [
                "Makes the smoothest smoothies I've ever had. No chunks, perfect consistency every time.",
                "Crushed ice like it was nothing. The {product} is a beast. {competitor} can't compare.",
                "This blender handles frozen fruit, nuts, seeds — everything. Incredibly powerful motor.",
            ],
            "usability": [
                "Love the preset programs. One button for smoothies, another for soups. So intuitive.",
                "Easy to clean — just add soap and water, hit pulse, done. Takes 30 seconds.",
                "The single-serve cups are a game changer for morning smoothies. Blend and go.",
            ],
        },
        "negative": {
            "durability": [
                "Blade assembly cracked after {months} months. Glass found in my smoothie. Dangerous.",
                "Motor burned out after {months} months of daily use. For this price, expected more.",
                "Rubber gasket at the base started leaking after {months} months. Messy and unsanitary.",
            ],
            "noise": [
                "Wakes up the entire apartment building when I make my morning smoothie. Insanely loud.",
                "The noise is brutal. I literally wear earplugs when blending. Not exaggerating.",
            ],
            "size": [
                "Too tall to fit under my kitchen cabinets. Have to store it in the pantry. Inconvenient.",
                "Takes up a huge amount of counter space. Not practical for small kitchens.",
            ],
        },
    },
    "air_fryers": {
        "positive": {
            "usability": [
                "The dual zone feature is brilliant. Cook chicken and fries at different temps simultaneously.",
                "So easy to use. Preset buttons for everything. Even my tech-challenged parents love it.",
                "Replaced my oven for 80% of meals. Faster, crispier, and uses way less energy.",
            ],
            "price_value": [
                "Best kitchen purchase I've made in years. Paid for itself in saved takeout within a month.",
                "Can't believe the quality for this price. {competitor} charges 3x for worse performance.",
            ],
            "cleaning": [
                "Non-stick baskets clean up in seconds. Just wipe and done. No soaking needed.",
                "Dishwasher safe baskets are a must-have feature. {brand} got this right.",
            ],
        },
        "negative": {
            "durability": [
                "Non-stick coating started peeling after {months} months. Had to throw it out. Not safe.",
                "The basket handle broke off while pulling it out. Nearly dropped hot food everywhere.",
                "Door hinge snapped after {months} months. Flimsy construction for daily use.",
            ],
            "size": [
                "The basket is smaller than advertised. Can't fit a whole chicken despite marketing claims.",
                "Exterior is massive but interior cooking space is disappointing. Misleading capacity specs.",
            ],
            "smell": [
                "Plastic smell when heating. Even after running it empty multiple times, still smells chemical.",
                "Food comes out tasting like plastic for the first few weeks. Concerning.",
            ],
        },
    },
    "coffee_makers": {
        "positive": {
            "usability": [
                "Makes barista-quality espresso at home. The built-in grinder is precise and consistent.",
                "Love the specialty brew options. Cold brew, over ice, classic — it does everything.",
                "Super easy to set up and use. Had great coffee within 10 minutes of unboxing.",
            ],
            "price_value": [
                "Saving $150/month on coffee shop visits. This {product} paid for itself in 2 months.",
                "Fraction of the cost of {competitor} but honestly produces better tasting coffee.",
            ],
        },
        "negative": {
            "durability": [
                "Leaks from the bottom after {months} months. Water everywhere on my counter every morning.",
                "The grinder jammed permanently after {months} months. $400 coffee maker is now a paperweight.",
                "Screen stopped working after {months} months. Can't select brew type without it.",
            ],
            "cleaning": [
                "Descaling is a nightmare. Takes 45 minutes and you need proprietary solution they sell separately.",
                "Milk frother clogs constantly. Have to deep clean it after every single use.",
                "Coffee grounds get stuck in every crevice. Disassembly for cleaning takes 15 minutes.",
            ],
            "usability": [
                "The water tank is awkward to remove and refill. Spill water every time.",
                "Touch screen is unresponsive. Takes multiple presses to register. Very frustrating first thing in the morning.",
            ],
        },
    },
}


def generate_synthetic_reviews(
    count: int = 5500,
    seed: int = 42,
) -> list[RawReview]:
    """Generate realistic synthetic reviews matching real-world distributions."""

    random.seed(seed)
    reviews: list[RawReview] = []
    today = date.today()

    categories = list(PRODUCT_CATALOG.keys())
    reviews_per_category = count // len(categories)

    for cat in categories:
        brands = PRODUCT_CATALOG.get(cat, {})
        all_products = []
        for brand, products in brands.items():
            for p in products:
                all_products.append((brand, p))

        for i in range(reviews_per_category):
            brand, product = random.choice(all_products)
            rating = _sample_rating()
            is_positive = rating >= 4
            sentiment_key = "positive" if is_positive else "negative"

            templates = REVIEW_TEMPLATES.get(cat, {}).get(sentiment_key, {})
            if not templates:
                continue

            theme = random.choice(list(templates.keys()))
            template_list = templates[theme]
            template = random.choice(template_list)

            competitors = [b for b in brands.keys() if b != brand]
            competitor = random.choice(competitors) if competitors else "the competition"
            months = random.choice([2, 3, 4, 5, 6, 8, 10, 12])

            text = template.format(
                brand=brand,
                product=product["name"],
                competitor=competitor,
                months=months,
            )

            # Add 1-3 detail sentences to make each review more unique
            num_details = random.randint(1, 3)
            for _ in range(num_details):
                text += " " + _add_detail(cat, theme, is_positive)

            review_date = today - timedelta(days=random.randint(1, 365))
            rid = hashlib.md5(f"{product['asin']}_{i}_{seed}".encode()).hexdigest()[:12]

            reviews.append(RawReview(
                review_id=f"syn_{rid}",
                product_id=product["asin"],
                product_name=product["name"],
                brand=brand,
                category=cat,
                rating=rating,
                title=_generate_title(rating, theme),
                review_text=text,
                date=review_date,
                verified_purchase=random.random() < 0.75,
                helpful_votes=_sample_helpful_votes(rating),
                source=Source.AMAZON,
                reviewer_name=f"Reviewer_{rid[:6]}",
                source_url=f"https://amazon.com/dp/{product['asin']}",
            ))

    random.shuffle(reviews)
    _save_raw(reviews)
    log.success(f"Generated {len(reviews)} synthetic reviews across {len(categories)} categories")
    return reviews


def _sample_rating() -> float:
    """Amazon J-curve: ~45% 5-star, ~15% 4-star, ~8% 3-star, ~8% 2-star, ~24% 1-star."""
    r = random.random()
    if r < 0.45:
        return 5.0
    elif r < 0.60:
        return 4.0
    elif r < 0.68:
        return 3.0
    elif r < 0.76:
        return 2.0
    else:
        return 1.0


def _sample_helpful_votes(rating: float) -> int:
    if rating <= 2:
        return random.choices([0, 1, 2, 3, 5, 10, 20, 50], weights=[30, 20, 15, 10, 10, 8, 5, 2])[0]
    return random.choices([0, 1, 2, 3, 5], weights=[50, 25, 15, 7, 3])[0]


def _generate_title(rating: float, theme: str) -> str:
    if rating >= 4:
        titles = [
            f"Great {theme}!", "Love it!", "Best purchase this year",
            "Exceeded expectations", "Worth every penny", "Highly recommend",
            f"Perfect {theme}", "5 stars deserved", "Amazing product",
        ]
    elif rating == 3:
        titles = [
            "Decent but has issues", "Mixed feelings", "Good enough I guess",
            f"OK {theme} but...", "3 stars - room for improvement",
        ]
    else:
        titles = [
            "Very disappointed", "Broke too quickly", "Don't buy this",
            f"Terrible {theme}", "Want my money back", "Returned it",
            "Save your money", f"Major {theme} problems", "Not as advertised",
        ]
    return random.choice(titles)


def _add_detail(category: str, theme: str, positive: bool) -> str:
    details = {
        True: [
            "Would buy again in a heartbeat.",
            "Bought one for my parents too.",
            "Way better than what I had before.",
            "The quality is evident from the packaging to the product itself.",
            "Setup was incredibly easy, took less than 5 minutes.",
            "My whole family loves it.",
            "Exceeded my expectations in every way.",
            "I've been recommending this to all my friends.",
            "It's become an essential part of my daily routine.",
            "After researching for weeks, so glad I picked this one.",
            "Even my skeptical husband admits it's great.",
            "Perfect size for our kitchen counter.",
            "The design looks premium and modern.",
            "Very impressed with the build quality.",
            "Customer service was responsive when I had a question.",
            "Great value compared to the higher-priced alternatives.",
            "I was hesitant because of some reviews but I'm really happy with it.",
            "Works exactly as advertised, maybe even better.",
            "This has completely changed how I approach cleaning.",
            "I've had mine for six months and it still works like new.",
            "The accessories that come with it are actually useful.",
            "Much better than the previous model I owned.",
            "I appreciate the thoughtful design touches.",
            "Energy efficient compared to my old one.",
            "The warranty gives me peace of mind.",
        ],
        False: [
            "Customer service was unhelpful when I called.",
            "This is my second unit — first one had the same problem.",
            "Reading other reviews, seems like a common issue.",
            "Wish I had gone with a different brand.",
            "Update: company sent a replacement but it has the same issue.",
            "Very disappointed given the price point.",
            "The materials feel cheap compared to competitors.",
            "Had to return it within the first week.",
            "Instructions were unclear and missing key steps.",
            "Not worth the money at all.",
            "My previous model lasted 5 years, this one barely made it 6 months.",
            "The warranty process was a nightmare.",
            "I expected much better from this brand.",
            "Several parts started rattling after a few weeks.",
            "It overheats during extended use.",
            "The attachments don't fit properly.",
            "Looks nothing like the pictures online.",
            "The first one arrived damaged, replacement has same quality issues.",
            "My neighbor has the competitor version and it's clearly better.",
            "I've spent more on replacement parts than the original cost.",
            "Performance has degraded significantly over time.",
            "The app that pairs with it is buggy and unreliable.",
            "Way too complicated for what should be a simple product.",
            "I should have read the 1-star reviews before buying.",
            "Build quality has clearly gone downhill from previous generations.",
        ],
    }
    return random.choice(details[positive])


def _save_raw(reviews: list[RawReview]):
    out = RAW_DIR / "synthetic_reviews.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in reviews:
            f.write(r.model_dump_json() + "\n")
    log.info(f"Saved to {out}")
