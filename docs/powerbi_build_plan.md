# Power BI Build Plan — Review Intelligence

A step-by-step, paste-ready plan to rebuild the **Executive Overview** and
**Competitive Intel** views (plus a **Trends** page) from the Streamlit dashboard
as a Power BI report.

**Data source:** the CSVs written by [`src/analysis/powerbi_export.py`](../src/analysis/powerbi_export.py)
into `reports/powerbi/`. Regenerate them any time with:

```bash
python -m src.analysis.powerbi_export
```

Every number is computed by `AnalysisEngine` (engine.py) and the same brand-health
formula used in `app.py`, so the report matches the Streamlit dashboard exactly.

---

## 1. Data model

### 1.1 Tables

| Table | Grain | Source in export |
|---|---|---|
| `fact_reviews` | one classified review | `build_fact_reviews()` |
| `dim_date` | one calendar day (contiguous) | `build_dim_date()` |
| `dim_brand` | one brand | `build_dim_brand()` |
| `dim_category` | one category | `build_dim_category()` |
| `agg_top_issues` | brand × theme × category (ranked) | `engine.top_issues_by_category()` |
| `agg_competitor_comparison` | our_brand × competitor × theme × category | `engine.competitor_comparison()` |
| `agg_emerging_issues` | category × theme (90-day window) | `engine.emerging_issues(days=90)` |

`fact_reviews` + the three `dim_` tables form a classic **star schema**. The three
`agg_` tables are pre-aggregated fact tables that mirror engine.py exactly — use
them for visuals whose logic lives in engine.py (impact ranking, sentiment deltas,
growth factors) so you never re-derive that logic in DAX.

### 1.2 Columns you will actually use

**`fact_reviews`** (grain = review): `review_id`, `brand`, `category`,
`product_name`, `rating` (1–5), `sentiment` (`positive`/`negative`/`mixed`/`neutral`),
`primary_theme`, `severity` (1–5), `verified_purchase` (bool), `review_date` (FK to
dim_date), `helpful_votes`, `competitor_mention_count`,
`competitor_brands_mentioned`, `is_shark_ninja`, `is_negative`, `is_positive`.

**`dim_date`**: `date` (key), `year`, `quarter`, `month_num`, `month_name`,
`month_year` (e.g. `Jan 2025`), `year_month_sort` (integer sort key), `day`.

**`dim_brand`**: `brand` (key), `is_shark_ninja`, `brand_type`
(`Shark/Ninja` | `Competitor`).

**`dim_category`**: `category` (key), `category_label` (e.g. `Air Fryers`).

**`agg_top_issues`**: `category`, `rank`, `brand`, `theme`, `frequency`,
`avg_severity`, `recency_weight`, `impact_score`, `top_failure_mode`,
`affected_products`, `sample_quote`.

**`agg_competitor_comparison`**: `category`, `our_brand`, `competitor`, `theme`,
`our_score`, `competitor_score`, `delta`, `our_sample_size`,
`competitor_sample_size`, `insight`, `opportunity`.

**`agg_emerging_issues`**: `category`, `theme`, `recent_count`, `older_count`,
`growth_factor`, `recent_severity_avg`.

### 1.3 Relationships

All are **single-direction, many-to-one** (fact/agg on the many side, dim on the
one side). Natural (business) keys — no surrogate keys needed at this scale.

| From (many) | To (one) | Column | Active? |
|---|---|---|---|
| `fact_reviews[brand]` | `dim_brand[brand]` | brand | ✅ active |
| `fact_reviews[category]` | `dim_category[category]` | category | ✅ active |
| `fact_reviews[review_date]` | `dim_date[date]` | date | ✅ active |
| `agg_top_issues[category]` | `dim_category[category]` | category | ✅ active |
| `agg_top_issues[brand]` | `dim_brand[brand]` | brand | ✅ active |
| `agg_competitor_comparison[category]` | `dim_category[category]` | category | ✅ active |
| `agg_emerging_issues[category]` | `dim_category[category]` | category | ✅ active |

> **Why `agg_competitor_comparison` only joins on `category`:** it has *two* brand
> columns (`our_brand`, `competitor`). Relating both to `dim_brand` creates an
> ambiguous/inactive-relationship mess. Keep those two columns as plain text and
> slice/pivot on them directly (they're the axes of the heatmap). A shared
> `dim_category` is enough to let one category slicer drive every page.

### 1.4 Setup steps in Power BI Desktop

1. **Get Data → Text/CSV**, import all seven CSVs from `reports/powerbi/`.
   (Or **Get Data → Folder** → point at `reports/powerbi/` and load all at once.)
2. In **Model view**, create the relationships in the table above (drag the `from`
   column onto the `to` column; set cardinality *Many to one* and cross-filter
   *Single*).
3. Select `dim_date` → **Table tools → Mark as date table** → choose `[date]`.
4. On `dim_date`, set **Sort by column**: sort `month_year` by `year_month_sort`.
5. Set data types: `rating`, `severity`, `*_score`, `delta`, `growth_factor` →
   Decimal/Whole number; `verified_purchase`, `is_*` → True/False;
   `review_date`/`date` → Date.
6. Create a `_Measures` table (**Enter Data**, one blank table) and put every
   measure below in it, so measures don't clutter the fact table.

---

## 2. DAX measures (paste-ready)

Put these in the `_Measures` table. Names match how they're referenced on pages.

### 2.1 KPI card measures (Executive Overview)

```DAX
Total Reviews = COUNTROWS ( fact_reviews )
```
```DAX
Avg Rating = AVERAGE ( fact_reviews[rating] )
```
```DAX
Negative Rate % =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[sentiment] = "negative" ),
    COUNTROWS ( fact_reviews )
) * 100
```
```DAX
Avg Severity = AVERAGE ( fact_reviews[severity] )
```
```DAX
Verified Rate % = AVERAGE ( fact_reviews[verified_purchase] ) * 100
```
```DAX
Distinct Products = DISTINCTCOUNT ( fact_reviews[product_name] )
```

> These reproduce the six KPI cards in `render_executive()`: Reviews, Avg Rating,
> Negative %, Severity, Verified %, Products.

### 2.2 Brand Health Score

Exact port of the scorecard formula in `app.py` (`render_executive`, the
`brand_stats["health_score"]` block). It rounds each component to 2 decimals and
the final score to a whole number, matching the Streamlit bar chart:

```DAX
Brand Health Score =
VAR AvgRating   = ROUND ( AVERAGE ( fact_reviews[rating] ), 2 )
VAR NegPct      = ROUND (
                    DIVIDE (
                        CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[sentiment] = "negative" ),
                        COUNTROWS ( fact_reviews )
                    ) * 100, 2 )
VAR AvgSeverity = ROUND ( AVERAGE ( fact_reviews[severity] ), 2 )
RETURN
    ROUND (
        AvgRating / 5 * 40
      + ( 100 - NegPct ) / 100 * 30
      + ( 5 - AvgSeverity ) / 4 * 30,
        0
    )
```

**Interpretation:** rating contributes 40 pts, low-negativity 30 pts, low-severity
30 pts → 0–100 scale.

Red/Yellow/Green banding (same thresholds as the Shark-vs-Ninja score circles in
app.py: `>=65` good, `>=45` ok, else bad):

```DAX
Brand Health RYG =
VAR S = [Brand Health Score]
RETURN SWITCH ( TRUE (), S >= 65, "Green", S >= 45, "Yellow", "Red" )
```

### 2.3 Sentiment Delta vs Competitor (heatmap)

The heatmap in `render_competitive()` is `pivot_table(index=competitor,
columns=theme, values=delta, aggfunc="mean")`. The `delta` is already computed by
`engine.competitor_comparison()` and lives in `agg_competitor_comparison`, so the
measure is just the mean of that column in the current cell context:

```DAX
Sentiment Delta = AVERAGE ( agg_competitor_comparison[delta] )
```

> **Do not** re-derive the delta in DAX. `delta = our_score − competitor_score`,
> where each score is `(sentiment_ratio + avg_rating/5) / 2` computed only when a
> brand has ≥3 reviews for that theme (see `engine._theme_score`). That min-sample
> gating won't survive a naive DAX rewrite — the pre-aggregated column is the
> source of truth.

*(Optional, illustrative only — the underlying theme score, if you ever want it on
`fact_reviews`; not used for the heatmap.)*
```DAX
Theme Score =
VAR Total = COUNTROWS ( fact_reviews )
VAR Pos   = CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[sentiment] = "positive" )
VAR Neg   = CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[sentiment] = "negative" )
RETURN DIVIDE ( DIVIDE ( Pos - Neg, Total ) + AVERAGE ( fact_reviews[rating] ) / 5, 2 )
```

### 2.4 Issue Growth Rate (emerging issues)

Mirrors `engine.emerging_issues()` `growth_factor` (= recent theme-rate ÷ older
theme-rate over a 90-day window), pre-computed in `agg_emerging_issues`:

```DAX
Issue Growth Rate = AVERAGE ( agg_emerging_issues[growth_factor] )
```

### 2.5 Issue Impact Score (issue ranking)

From `agg_top_issues` (= `engine.top_issues_by_category()` `impact_score`,
frequency × avg severity × recency weight):

```DAX
Issue Impact Score = SUM ( agg_top_issues[impact_score] )
```

---

## 3. Report pages

Three pages mapped to the existing Streamlit tabs. Add a shared **Category slicer**
(`dim_category[category_label]`) and a **Brand slicer** (`dim_brand[brand]`) to
pages 1 and 3; sync them via **View → Sync slicers**.

### Page 1 — Executive Overview  *(Streamlit `render_executive`)*

| Element | Visual type | Fields / measures |
|---|---|---|
| 6 KPI cards | **Card** (×6) | `[Total Reviews]`, `[Avg Rating]`, `[Negative Rate %]`, `[Avg Severity]`, `[Verified Rate %]`, `[Distinct Products]` |
| Brand Health Scorecard | **Clustered bar chart** (horizontal) | Axis `dim_brand[brand]`, Value `[Brand Health Score]`, sort descending |
| — R/Y/G scorecard | **Matrix** | Rows `dim_brand[brand]`; Values `[Brand Health Score]`, `[Avg Rating]`, `[Negative Rate %]`, `[Avg Severity]`; conditional-format the score cell by `[Brand Health RYG]` (see below) |
| Issue Theme Breakdown | **Donut chart** | Legend `fact_reviews[primary_theme]`, Value `[Total Reviews]`, filter `fact_reviews[sentiment] IN {"negative","mixed"}` (visual-level filter) |
| Shark vs Ninja | **Card** ×2 + **Column chart** ×2 | Filter page/visual to `is_shark_ninja = True`; cards show `[Brand Health Score]`, columns show count by `rating` |

**KPI "Good/Watch" coloring** (matches app.py deltas): use conditional formatting
on the cards — Avg Rating green if ≥3.5; Negative Rate red if >30; Avg Severity red
if >3.

**R/Y/G conditional formatting:** on the matrix, Value → *Conditional formatting →
Background color → Format by: Field value* → point at a color measure:

```DAX
Brand Health Color =
SWITCH ( [Brand Health RYG], "Green", "#3FB950", "Yellow", "#D29922", "Red", "#F85149" )
```

To highlight Shark/Ninja like the gold outline in Streamlit, add a data-color rule
using `dim_brand[is_shark_ninja]`.

### Page 2 — Competitive Intel  *(Streamlit `render_competitive`)*

| Element | Visual type | Fields / measures |
|---|---|---|
| Category slicer | **Slicer** | `dim_category[category_label]` (single-select) |
| Competitive heatmap | **Matrix** | Rows `agg_competitor_comparison[competitor]`, Columns `agg_competitor_comparison[theme]`, Values `[Sentiment Delta]` |
| "Where We Lag" | **Clustered bar / Table** | `agg_competitor_comparison` filtered `delta < -0.1`, sorted ascending, top 5; show `theme`, `competitor`, `delta` |
| "Where We Lead" | **Clustered bar / Table** | same table filtered `delta > 0.1`, sorted descending, top 5 |

**Heatmap coloring** (matches the Streamlit diverging red→green centered at 0):
select the matrix → Values → *Conditional formatting → Background color* →
*Format style: Diverging*, Minimum `#F85149` (red), Center `0` → dark/neutral,
Maximum `#3FB950` (green). Green = Shark/Ninja advantage, red = competitor
advantage — add that as a caption text box.

### Page 3 — Trends & Signals  *(Streamlit `render_trends`)*

| Element | Visual type | Fields / measures |
|---|---|---|
| Monthly sentiment trend | **Stacked area chart** | Axis `dim_date[month_year]` (sorted by `year_month_sort`), Legend `fact_reviews[sentiment]`, Value `[Total Reviews]` |
| Monthly rating by brand | **Line chart** | Axis `dim_date[month_year]`, Legend `dim_brand[brand]`, Value `[Avg Rating]` (Y-axis fixed 1–5) |
| Emerging issues | **Clustered bar chart** (horizontal) | Axis `agg_emerging_issues[theme]`, Value `[Issue Growth Rate]`, Legend `agg_emerging_issues[category]` |

> Because `dim_date` is a marked, contiguous date table you also get free
> time-intelligence (MTD, prior-period, rolling averages) if you want to extend the
> Trends page beyond what Streamlit shows.

---

## 4. Consistent theming (optional, matches the Streamlit look)

Save this as `sharkninja_theme.json` and import via **View → Themes → Browse for
themes**. Brand hex values are lifted from `app.py`'s `BRAND_COLORS`.

```json
{
  "name": "SharkNinja Review Intel",
  "dataColors": ["#14a3a8", "#e8863a", "#a371f7", "#58a6ff", "#3fb950",
                 "#f85149", "#d29922", "#bc8cff", "#79c0ff", "#56d364"],
  "background": "#0e1117",
  "foreground": "#e6edf3",
  "tableAccent": "#0d7377"
}
```

Sentiment colors to set manually on the trend/donut legends: positive `#3fb950`,
negative `#f85149`, mixed `#d29922`, neutral `#8b949e`.

---

## 5. Validation checklist

After building, confirm the report matches Streamlit / engine.py:

- [ ] **Total Reviews** card = review count in the Streamlit header (e.g. 4,800 on demo data).
- [ ] **Brand Health Score** per brand = the horizontal bar values on the Streamlit exec tab.
- [ ] **Sentiment Delta** heatmap cells = the Streamlit competitive-intel heatmap for the same category.
- [ ] **Issue Growth Rate** bars = `growth_factor` in `agg_emerging_issues.csv`.
- [ ] Shark & Ninja are visually distinguished on the scorecard.

Numbers are guaranteed to match because the aggregates come straight from
`AnalysisEngine`; if they don't, re-run `python -m src.analysis.powerbi_export` to
refresh the CSVs.
