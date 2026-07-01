# Review Intelligence

An automated pipeline that ingests consumer product reviews, classifies them with Claude, and surfaces product issues, competitive gaps, and PM-ready recommendations through an interactive dashboard.

Built for SharkNinja's product categories: vacuums, blenders, air fryers, and coffee makers. Tracks 11 brands across Shark, Ninja, and their competitors (Dyson, iRobot, Vitamix, Keurig, etc.).

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)

## What it does

The system answers three questions a product manager actually cares about:

1. **What's breaking?** Top issues ranked by severity x frequency x recency, with customer quotes and affected products.
2. **How do we compare?** Theme-by-theme comparison against competitors. Where we lead, where we lag, and what features customers praise in competitors but not in our products.
3. **What's getting worse?** Emerging issues that grew in the last 90 days, products with return-risk signals, and sentiment trends over time.

The output is a Streamlit dashboard with 6 tabs (executive overview, issue drill-down, competitive intel, product explorer, trends, and data export) plus Excel files formatted for Tableau.

## How it works

Five phases, each independent. You can run them together or one at a time.

### Phase 1: Ingestion

Three data sources, any combination:

- **Amazon** via Apify. Iterates through ASINs in the product catalog, pulls reviews with ratings, dates, and verified-purchase flags.
- **Reddit** via PRAW. Scans 12 subreddits (r/VacuumCleaners, r/Blenders, r/Coffee, etc.) for posts mentioning tracked brands. Uses keyword matching to assign brand and category.
- **Synthetic generator** for development. Produces ~5,500 reviews with Amazon's J-curve rating distribution (45% five-star, 24% one-star). Uses ~50 template sentences with randomized detail inserts so reviews survive fuzzy dedup.

Source: `src/ingestion/`

### Phase 2: Cleaning + Classification

**Cleaning pipeline** (`src/cleaning/pipeline.py`):
- Drops reviews under 20 characters
- Exact dedup via MD5 hash
- Fuzzy dedup via rapidfuzz (threshold: 95% similarity)
- Language detection with langdetect (English only)
- Spam detection: regex patterns for promotional URLs, bot-like repetition, excessive caps
- Flags shipping-only complaints (useful but not product issues)
- Text normalization: lowercases for matching, preserves original for display

From 5,500 synthetic reviews, roughly 4,800 survive (87% retention).

**LLM classification** (`src/classification/classifier.py`):
- Sends each review to Claude with a structured prompt that extracts 12 fields: primary theme, sentiment, severity (1-5), failure mode, failure timeline, competitor mentions, features mentioned, actionable signal, and key phrases.
- Routes edge cases to a stronger model: 3-star reviews (ambiguous sentiment), reviews over 1,000 characters (needs more context), and reviews with mixed signals.
- Runs in batches with a semaphore (max 10 concurrent calls) and caches responses with diskcache using SHA-256 keys to avoid re-classifying the same review.
- Tracks cost against a $50 budget cap.
- Includes a self-consistency check: re-classifies 100 random reviews and measures agreement rate.

**Classification evaluator** (`src/classification/evaluator.py`):
- Hallucination check: verifies that key phrases in the classification actually appear in the review text
- Feature grounding: confirms mentioned features exist in the original review
- Sentiment-rating alignment: flags reviews where a 5-star rating got classified as negative
- Severity distribution: checks for unrealistic clustering
- Coverage stats: percentage of reviews with actionable signals, failure modes, competitor mentions

### Phase 3: Analysis

`src/analysis/engine.py` runs eight analyses on the classified data:

| Analysis | What it computes |
|----------|-----------------|
| Top issues | Groups by brand + theme + category. Scores each by `severity * frequency * recency_weight`, where recency uses exponential decay over 180 days. Returns top issues per category with sample quotes and affected products. |
| Competitor comparison | For each (category, theme) pair, computes Shark/Ninja's average sentiment score vs. each competitor. Returns the delta, sample sizes, and a text insight. |
| Emerging issues | Compares theme frequency in the last 90 days vs. the prior period. Flags anything with a growth factor above 1.5x. |
| Feature gaps | Finds themes where competitors get positive reviews but Shark/Ninja doesn't. These are features customers want that we might not offer. |
| Return risk | Identifies products with high concentrations of severity-4+ negative reviews. These are candidates for returns. |
| Language patterns | Extracts common phrases from negative reviews per brand. Useful for CS script writing. |
| Verified vs. unverified | Compares average ratings and sentiment between verified and unverified purchases. Unverified reviews skew more extreme. |
| Summary stats | Total counts, date ranges, category breakdowns. |

### Phase 4: Recommendations

`src/recommendations/generator.py` sends analysis results to Claude Sonnet and asks for four parallel outputs:

- **Engineering fixes**: specific product changes ranked by impact
- **Marketing angles**: messaging opportunities based on where we lead competitors
- **CS scripts**: response templates for the top complaint themes, using actual customer language
- **Executive scorecard**: one-page summary with red/yellow/green status per category

Then generates a PM brief that ties it all together.

### Phase 5: Dashboard + Export

**Streamlit dashboard** (`src/dashboard/app.py`):
- Executive overview with KPI cards, brand health scores (0-100), and a Shark vs. Ninja comparison
- Issue deep-dive with impact-scored issues, expandable cards, and customer quotes
- Competitive heatmap showing advantage/disadvantage by theme per competitor
- Product explorer: drill into any product's rating distribution, complaint themes, and failure modes
- Trend charts: monthly sentiment over time, brand rating trends, emerging issues
- Data table with search, sort, and CSV export (full dataset, negative-only, summary pivot)

Sidebar filters for category, brand, sentiment, severity, and verified-purchase status.

**Tableau export** (`src/analysis/tableau_export.py`): Writes Excel files with four worksheets, formatted for direct import into Tableau.

## Project structure

```
review-intel/
  config/
    settings.py          # All configuration: API keys, model names, product catalog
  src/
    ingestion/
      amazon.py          # Apify-based Amazon scraper
      reddit.py          # PRAW Reddit scraper
      synthetic.py       # Synthetic review generator
    cleaning/
      pipeline.py        # Dedup, spam, language, normalization
    classification/
      classifier.py      # Async LLM classification with routing
      evaluator.py       # Hallucination and quality checks
    analysis/
      engine.py          # Eight analysis functions
      tableau_export.py  # Excel export for Tableau
    recommendations/
      generator.py       # LLM-powered recommendation generation
    dashboard/
      app.py             # Streamlit web dashboard
    utils/
      schema.py          # Pydantic models (RawReview, ClassifiedReview, etc.)
      llm.py             # Async Claude client with caching and cost tracking
      logging.py         # Rich console logging
  prompts/
    classification_v1.txt  # Classification prompt template
  tests/
    test_schema.py       # 4 tests
    test_cleaning.py     # 4 tests
    test_synthetic.py    # 5 tests
  scripts/
    run_full.bat         # Windows convenience script
    run_full.sh          # Unix convenience script
  run_demo.py            # Full pipeline with synthetic data, no API keys
  run_pipeline.py        # Full pipeline with CLI args
  .env.example           # API key template
```

## Quick start

### Demo mode (no API keys)

```bash
python run_demo.py
streamlit run src/dashboard/app.py
```

This generates 5,500 synthetic reviews, cleans them down to ~4,800, runs simulated classification (keyword-based, no LLM), and produces a working dashboard at `localhost:8501`.

### Full pipeline (requires API keys)

1. Copy `.env.example` to `.env` and add your keys:
   - `ANTHROPIC_API_KEY` (required for classification and recommendations)
   - `APIFY_API_TOKEN` (required for Amazon scraping)
   - `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` (required for Reddit scraping)

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Run:
   ```bash
   # Synthetic data + real LLM classification
   python run_pipeline.py

   # Live scraping + LLM classification
   python run_pipeline.py --live

   # Single phase
   python run_pipeline.py --phase classify

   # With consistency check
   python run_pipeline.py --consistency-check
   ```

4. Launch dashboard:
   ```bash
   streamlit run src/dashboard/app.py
   ```

## Configuration

Everything lives in `config/settings.py`. Key settings:

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `classification_model` | `claude-haiku-4-5-20251001` | Bulk classification model |
| `edge_case_model` | `claude-sonnet-5` | Model for ambiguous reviews |
| `recommendation_model` | `claude-sonnet-5` | Recommendation generation |
| `max_concurrent_llm` | `10` | Concurrent API calls |
| `llm_budget_usd` | `50.0` | Hard cost cap |
| `target_review_count` | `5000` | Target for synthetic generation |

The product catalog maps ASINs to canonical product names across 4 categories and 11 brands (20 products total).

## Tests

```bash
pytest
```

13 tests covering schema validation, cleaning pipeline behavior, and synthetic data generation.

## Dependencies

Python 3.12+. Key libraries: anthropic, pandas, plotly, streamlit, pydantic, rapidfuzz, langdetect, diskcache, apify-client, praw, openpyxl. Full list in `pyproject.toml`.
