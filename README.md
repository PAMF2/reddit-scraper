# reddit-scraper

Python scraper for Reddit focused on combat sports (MMA, boxing, BJJ, wrestling). Extracts posts, full comment threads, sentiment scores, news/leak detection, and optional Claude AI analysis. All from the public Reddit JSON API with no auth required.

## Features

| Feature | Detail |
|---|---|
| **Posts via JSON API** | ~1s per request, supports >100 posts with automatic pagination |
| **Full comment threads** | 250+ comments per post via Reddit's undocumented JSON endpoint |
| **Nested thread tree** | Replies correctly nested by depth; `max_comments` caps total (not top-level) |
| **Sentiment analysis** | Per-comment VADER scoring tuned for fight-community slang |
| **News & leak detection** | Keyword classifier tags posts as `NEWS / RESULT / LEAK / HYPE` |
| **Notable comment extraction** | Surfaces high-score comments containing news/result/leak keywords |
| **Claude AI analysis** | Summarizes discussions, extracts fighters, key topics, notable quotes |
| **Statistical distributions** | Score/sentiment distributions, cross-analysis (score tier x sentiment, depth x sentiment) |
| **Multi-subreddit** | Scrape several subs in one command, merged into one JSON |
| **Clean CSV output** | HTML entities decoded, newlines collapsed, no multiline cells |
| **Auto fallback** | If JSON API fails, switches to stealth Chromium browser |

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/PAMF2/reddit-scraper.git
cd reddit-scraper
pip install -r requirements.txt
scrapling install   # downloads Chromium (~150MB, one-time, only needed for browser fallback)
```

## Commands

### `posts` — list subreddit posts

```bash
python main.py posts --sub MMA --sort hot --limit 25
```

Posts are tagged with detected categories (e.g. `[NEWS/RESULT]`).

```
 1. [  1649] [ 266]  Firas Zahabi invites Khamzat Chimaev to train...
       WinterStill4472 | 2026-05-13 | streamable.com

 2. [   871] [ 189]  Sean Strickland reveals shoulder injury  [NEWS/RESULT]
       Difficult-Tree2738 | 2026-05-13 | i.redd.it
```

### `comments` — scrape a single post's comments

```bash
python main.py comments \
  --url "https://www.reddit.com/r/MMA/comments/1tc3j00/..." \
  --max-comments 250 \
  --sentiment
```

With `--sentiment`, each comment shows its score and polarity:

```
[u/Savage_Batmanuel  score:+591  2026-05-13  (+) +0.74]
  I forgot how good Lyoto was.

  [u/NukeTheWhales85  score:+184  2026-05-13  (+) +0.51]
    He really was fascinating to watch in his early years...

THREAD SENTIMENT: POSITIVE  avg=+0.082  (pos=24 neg=12 neu=4)

NOTABLE COMMENTS (8 found):
  [RESULT] u/chemo92 +256: Turn up the volume, you can hear Machida wheezing...
  [HYPE]   u/PinkSkies87 +38: This is such an iconic Rogan call...
```

### `scrape` — posts + comments in one shot

```bash
# Single subreddit
python main.py scrape --sub MMA --sort hot --limit 10 --max-comments 200 --sentiment

# Multiple subreddits
python main.py scrape --subreddits MMA ufc boxing bjj --sort hot --limit 5 --max-comments 100

# With Claude AI analysis (requires ANTHROPIC_API_KEY)
python main.py scrape --sub MMA --limit 5 --analyze --api-key sk-ant-...
```

Saves per-post comment CSVs + one merged JSON:
- `output/posts_MMA_<ts>.csv`
- `output/comments_<post_id>_<ts>.csv` (one per post, with optional `sentiment` columns)
- `output/full_MMA_<ts>.json` (everything nested)

### `news` — breaking news, leaks, and results only

```bash
python main.py news \
  --subreddits MMA ufc boxing \
  --sort new \
  --limit 50 \
  --categories news leak result
```

Scans 50 recent posts per subreddit and shows only those matching combat sports news keywords. Supports `--comments` to also fetch notable comments for each matched post.

```
r/MMA: 15/50 posts matched
r/ufc: 10/50 posts matched

 3. [  35] [  2]  Exclusive: PFL Africa Champion Abraham Bably to Face...  [NEWS/RESULT/LEAK]
 5. [ 871] [189]  Sean Strickland reveals shoulder injuries before fight  [RESULT]
14. [ 981] [533]  Khamzat Chimaev's brother says his body "shut down"    [NEWS]
```

### `stats` — score/sentiment distributions and cross-analysis

```bash
python main.py stats --file output/full_MMA_20260514.json
```

Reads a saved `full_*.json` file and prints five tables:

- **Post score distribution** (mean, median, stdev, p25/p75/p95, max)
- **Comment sentiment distribution** (avg compound, stdev, p25/p75, positive/negative/neutral counts)
- **Sentiment by score tier** (are comments under viral posts more positive?)
- **Sentiment by comment depth** (does tone change deeper in threads?)
- **Most active commenters** (top 10 by comment count)

```
  Post Score Distribution
  Stat      Value
  n             4
  mean      146.5
  median    132.0
  stdev    93.376
  p25       72.25
  p95      247.65

  Comment Sentiment  n=253
  POSITIVE  ▰▰▰▰▰▰▰▱▱▱▱▱  avg +0.097
  116 positive (45%)  75 negative (29%)  62 neutral (24%)

  Sentiment by Post Score Tier
  Score tier   Comments   Avg compound
  0-100              84         +0.066
  101-500           169         +0.112

  Sentiment by Comment Depth
  Depth      Comments   Avg compound
  depth 0         107         +0.069
  depth 1          65         +0.063
  depth 2          48         +0.107
  depth 4+         13         +0.470
```

Pass `--output <dir>` to also save a `stats_*.json` file with all raw numbers.

### `analyze` — Claude AI analysis on saved data

```bash
# Set your key (one-time)
set ANTHROPIC_API_KEY=sk-ant-...

# Analyze a previously saved full_*.json file
python main.py analyze --file output/full_MMA_20260514.json --limit 5
```

Output:

```
======================================================================
  CLAUDE ANALYSIS: Khamzat Chimaev's brother says body "shut down"
======================================================================

SUMMARY
  The community is reacting to news that Khamzat Chimaev suffered a
  severe health episode during training, raising questions about his
  long-term career prospects and future title shot timeline.

SENTIMENT: NEGATIVE
  The community expresses concern and disappointment over Khamzat's
  health, mixed with skepticism about whether this affects his UFC plans.

[BREAKING NEWS] Khamzat Chimaev suffered a serious physical health
episode during training camp, according to his brother.

FIGHTERS MENTIONED: Khamzat Chimaev, Sean Strickland, Dricus du Plessis

KEY TOPICS:
  - Fighter health and safety
  - Title shot implications
  - UFC matchmaking speculation
  - Khamzat's training intensity

NOTABLE QUOTES:
  "You can't fake that kind of shutdown. Hope he recovers fully."
  "This is why I've always said the UFC pushes fighters too hard."
```

## CLI reference

```
usage: main.py [-h] [--output OUTPUT] {posts,comments,scrape,news,analyze,stats} ...

subcommands:
  posts      List posts from a subreddit
  comments   Scrape comments from a single post URL
  scrape     Scrape posts + comments (one or more subreddits)
  news       Show only breaking news, leaks, results, and hype posts
  analyze    Run Claude AI analysis on a saved full_*.json file
  stats      Score/sentiment distributions + cross-analysis on a full_*.json file

options:
  --output, -o   Output directory (default: output/)

posts:
  --sub          Subreddit              (default: MMA)
  --sort         hot|new|top|rising     (default: hot)
  --limit        Max posts              (default: 25)
  --method       auto|api|browser       (default: auto)

comments:
  --url          Full Reddit post URL   (required)
  --max-comments Total comments         (default: 500, all depths)
  --depth        Max display depth      (default: 3)
  --sentiment    Add sentiment scores
  --min-score    Min upvotes for notable detection (default: 5)
  --method       auto|api|browser

scrape:
  --sub          Subreddit              (default: MMA)
  --subreddits   Multiple subs          (e.g. --subreddits MMA ufc boxing)
  --sort         hot|new|top|rising     (default: hot)
  --limit        Posts per subreddit    (default: 10)
  --max-comments Total comments/post    (default: 200)
  --depth        Max display depth      (default: 3)
  --sentiment    Add sentiment scores
  --analyze      Run Claude AI analysis (requires --api-key or ANTHROPIC_API_KEY)
  --api-key      Anthropic API key
  --model        Claude model           (default: claude-haiku-4-5-20251001)
  --method       auto|api|browser

news:
  --sub          Subreddit              (default: MMA)
  --subreddits   Multiple subs
  --sort         hot|new|top|rising     (default: new)
  --limit        Posts to scan          (default: 50)
  --categories   news|result|leak|hype  (default: all)
  --comments     Also fetch comments for matched posts
  --comments-limit   Max posts to fetch comments for (default: 5)
  --method       auto|api|browser

analyze:
  --file         Path to full_*.json file (required)
  --limit        Max posts to analyze    (default: 10)
  --api-key      Anthropic API key
  --model        Claude model            (default: claude-haiku-4-5-20251001)

stats:
  --file         Path to full_*.json file (required)
  --output       Save stats_*.json to this directory (optional)
```

### `--method` options

| value | behavior |
|---|---|
| `auto` | JSON API first; browser fallback on failure |
| `api` | JSON API only, fast, 1s/request, 250+ comments |
| `browser` | StealthyFetcher, ~10s/request, ~25 results/page |

## Output formats

### posts CSV

| field | example |
|---|---|
| id | t3_1tc3j00 |
| title | Jon Jones submits Lyoto Machida... |
| author | airplane231 |
| score | 1502 |
| comment_count | 278 |
| domain | imgur.com |
| permalink | https://www.reddit.com/r/MMA/... |
| content_href | https://imgur.com/... |
| post_type | link |
| created | 2026-05-13 |
| upvote_ratio | 0.964 |
| subreddit | r/MMA |

### comments CSV

| field | example |
|---|---|
| post_id | t3_1tc3j00 |
| comment_id | t1_ollb90u |
| parent_id | (empty = top-level) |
| depth | 0 |
| author | Savage_Batmanuel |
| score | 591 |
| created | 2026-05-13 |
| body | I forgot how good Lyoto was. |
| permalink | https://www.reddit.com/r/MMA/... |
| sentiment | positive *(with --sentiment)* |
| sentiment_compound | +0.735 *(with --sentiment)* |
| sentiment_intensity | strong *(with --sentiment)* |

### full JSON structure

```json
[
  {
    "post": { "id": "t3_1tc3j00", "title": "...", "score": 1502 },
    "sentiment": { "avg_compound": 0.082, "label": "positive", "distribution": {} },
    "claude_analysis": { "summary": "...", "fighter_mentions": [] },
    "comments": [
      {
        "id": "t1_ollb90u",
        "author": "Savage_Batmanuel",
        "score": 591,
        "depth": 0,
        "body": "I forgot how good Lyoto was.",
        "created": "2026-05-13",
        "permalink": "...",
        "replies": []
      }
    ]
  }
]
```

## Code structure

```
reddit-scraper/
├── main.py                  # CLI: posts / comments / scrape / news / analyze / stats
├── requirements.txt
├── scraper/
│   ├── __init__.py          # public API exports
│   ├── fetcher.py           # StealthyFetcher wrapper with retry (browser fallback)
│   ├── reddit_api.py        # JSON API: posts + comments, HTML cleaning, pagination
│   ├── posts.py             # get_posts() with auto/api/browser routing
│   ├── comments.py          # get_comments() with auto/api/browser routing
│   ├── sentiment.py         # VADER + fight-lexicon overrides, thread aggregation
│   ├── news.py              # keyword classifier: news / result / leak / hype
│   ├── analyzer.py          # Claude AI: post summarizer, fighter extractor
│   ├── stats.py             # score/sentiment distributions + cross-analysis
│   ├── display.py           # Rich terminal UI (tables, panels, colored text)
│   └── export.py            # JSON / CSV / console output (with optional sentiment cols)
├── results/                 # sample scraped outputs committed to the repo
│   ├── sample_posts_MMA_boxing.csv
│   ├── sample_comments_MMA_boxing.csv    # with sentiment scores
│   ├── sample_full_MMA_boxing.json       # nested posts + comments
│   └── sample_stats_MMA_boxing.json      # statistical report
└── output/                  # your generated files (gitignored)
```

## Results

The `results/` folder contains sample outputs scraped from r/MMA and r/boxing (May 2026).

### `sample_posts_MMA_boxing.csv` — 4 posts

| id | title | score | comment_count | upvote_ratio |
|---|---|---|---|---|
| t3_1tcmu2x | Is MVP the McDonald's of MMA? | 258 | 97 | 0.95 |
| t3_1t7fb5f | MVP MMA: Rousey vs Carano Open Workouts | 7 | 48 | 0.86 |
| t3_1td0ruj | Usyk sparring session for Rico fight in Egypt. | 144 | 23 | 0.95 |
| t3_1tcq38n | Terence Crawford on Naoya Inoue... | 121 | 7 | 0.96 |

### `sample_comments_MMA_boxing.csv` — 253 comments (with sentiment)

| comment_id | author | score | depth | sentiment | sentiment_compound | body |
|---|---|---|---|---|---|---|
| t1_old4klb | Davemeddlehed | 27 | 0 | positive | +0.643 | McDonalds is quality... |
| t1_old8wmo | Maxiuss456 | 15 | 1 | neutral | +0.000 | Yeah this exactly... |

### `sample_stats_MMA_boxing.json` — statistical report

```json
{
  "posts": {
    "count": 4,
    "score": { "mean": 146.5, "median": 132.0, "stdev": 93.376, "p95": 247.65 },
    "upvote_ratio": { "mean": 0.93, "median": 0.955 }
  },
  "comments": {
    "count": 253,
    "sentiment_compound": { "mean": 0.097, "stdev": 0.476, "p25": -0.253, "p75": 0.459 },
    "sentiment_dist": { "positive": 116, "negative": 75, "neutral": 62 }
  },
  "cross": {
    "score_tier_sentiment": {
      "0-100":   { "avg_compound": 0.066, "n": 84 },
      "101-500": { "avg_compound": 0.112, "n": 169 }
    },
    "depth_sentiment": {
      "depth_0": { "avg_compound": 0.069, "n": 107 },
      "depth_4": { "avg_compound": 0.470, "n": 13 }
    }
  }
}
```

Key findings from this sample:
- **45% of comments are positive**, 29% negative — MMA fans skew positive in hot threads
- **Higher-score posts attract more positive comments** (avg +0.112 vs +0.066 in low-score posts)
- **Deep replies (depth 4+) are the most positive** (avg +0.470) — fans who reply deeply tend to be more engaged and enthusiastic
- **Stdev of 0.476** reflects high variance — MMA comment sentiment is polarized, not uniform

## How it works

### Posts and comments via JSON API

Reddit exposes unauthenticated JSON endpoints:

```
GET https://www.reddit.com/r/{sub}/hot.json?limit=100
GET https://www.reddit.com/r/{sub}/comments/{id}.json?limit=500
    User-Agent: Mozilla/5.0 Chrome/124...
```

The post listing supports `after` cursor pagination for limits > 100. The comment endpoint returns the full nested tree in one request (~250 comments per post; skips deleted/removed entries).

### Sentiment via VADER + fight lexicon

The [VADER](https://github.com/cjhutto/vaderSentiment) lexicon was built for social media but doesn't handle fight-community slang well ("savage", "nasty", "beast" score as negative). This scraper adds a custom lexicon layer with fight-appropriate scores:

| word | VADER default | overridden to |
|---|---|---|
| `goat` | neutral | +2.5 |
| `savage`, `beast` | negative | +1.8 to +2.0 |
| `nasty`, `filthy` | negative | +1.0 (fight context) |
| `robbed` | neutral | -2.0 |
| `boring` | negative | -2.0 |
| `juicer`, `cheater` | neutral | -1.5 to -2.0 |

Per-comment scores range from -1.0 (very negative) to +1.0 (very positive). Thread-level analysis aggregates all comments and returns a distribution + average compound score.

### News and leak detection

A regex classifier runs against post titles and comment bodies, tagging content into:

- **`news`** — breaking, announced, report, confirmed, injury, retirement, drug test, suspension...
- **`result`** — KO, TKO, submission, decision, champion, title shot, belt, stoppage...
- **`leak`** — leaked, exclusive, source says, reportedly, insider, rumored...
- **`hype`** — GOAT, fight of the year, legendary, iconic, greatest ever...

### Claude AI analysis

When `--analyze` is set, each post's top 80 comments are serialized into a structured prompt sent to Claude. The response is parsed into:
- Summary of the discussion
- Overall community sentiment + reasoning
- Fighter names mentioned
- Key topics (judging, PEDs, technique, matchmaking...)
- Notable quotes verbatim
- Breaking news flag + one-line summary

Uses `claude-haiku` by default (fast, cheap). Switch to `claude-sonnet-4-6` for deeper analysis.

### Browser fallback

When the JSON API is blocked (403) or `method="browser"` is set, the scraper launches a real Chromium instance via [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) with patched fingerprints to bypass Reddit's anti-bot detection.

## Combat sports subreddits

| subreddit | content |
|---|---|
| r/MMA | General MMA (UFC, Bellator, ONE, PFL) |
| r/ufc | UFC-specific discussion and results |
| r/boxing | Professional boxing, all promotions |
| r/bjj | Brazilian Jiu-Jitsu technique and competition |
| r/wrestling | Amateur and pro wrestling |
| r/kickboxing | Kickboxing (K-1, Glory, ONE) |
| r/WMMA | Women's MMA |
| r/mmamemes | Post-event reactions and memes |
| r/fightporn | Amateur and street fight videos |

## Next steps

### ML sentiment classifier (scikit-learn)

VADER is lexicon-based and has no memory of context. A trained classifier on scraped data would be more accurate for MMA-specific language:

```python
# 1. Build a labeled dataset from scraped CSVs
#    Use sentiment_compound as the soft label (regression) or bucket into 3 classes
df = pd.read_csv("results/sample_comments_MMA_boxing.csv")
df["label"] = df["sentiment_compound"].apply(
    lambda c: "positive" if c >= 0.05 else ("negative" if c <= -0.05 else "neutral")
)

# 2. Train a TF-IDF + LogisticRegression pipeline
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=20000)),
    ("clf",   LogisticRegression(C=5, max_iter=1000)),
])
model.fit(df["body"], df["label"])

# 3. Swap into scraper/sentiment.py as an optional backend
#    Falls back to VADER when model file is not present
```

The trained model can be serialized with `joblib.dump()` and loaded at startup in `sentiment.py`. Requires `scikit-learn pandas joblib` in requirements.

### Hype indicator

The current `HYPE` tag is binary (keyword match / no match). A regression score from a trained model would rank posts on a continuous hype scale, useful for surfacing genuinely viral discussions before they peak:

```python
# Features: upvote_ratio, score_velocity (score / post_age_hours),
#           avg_comment_depth, fraction_positive, hype_keyword_count
# Target: final_score (scraped 24h later as ground truth)

from sklearn.ensemble import GradientBoostingRegressor
hype_model = GradientBoostingRegressor(n_estimators=200)
hype_model.fit(X_train, y_score)

# Output: post.hype_score = float 0.0-1.0, shown in the posts table
```

### OpenClaw integration

This scraper can feed a Claude plugin (MCP server or OpenClaw-style tool) so Claude can answer fight questions with live Reddit context:

```
User: "What's Reddit saying about the Poirier vs Holloway fight today?"

Claude calls: reddit_scraper.news(subreddits=["MMA","ufc"], sort="new", limit=50)
           + reddit_scraper.comments(top_post_url, max_comments=100)
           + reddit_scraper.analyze(post, comments)

Claude returns: structured summary with sentiment, notable quotes, breaking news flag
```

The MCP server would expose three tools: `get_posts`, `get_comments`, and `analyze_post`. A Claude Desktop or OpenClaw plugin config would look like:

```json
{
  "mcpServers": {
    "reddit-fight-intel": {
      "command": "python",
      "args": ["mcp_server.py"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```

This turns the scraper into a live fight intelligence feed for any Claude-powered assistant.

## License

MIT
