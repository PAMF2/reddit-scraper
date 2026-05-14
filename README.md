# reddit-scraper

A Python scraper for Reddit that extracts posts and full threaded comment trees from any subreddit — built specifically for combat sports analysis (MMA, boxing, BJJ, etc.).

Uses Reddit's public JSON API as the primary method (fast, 200+ comments per thread) with a stealth headless browser ([Scrapling](https://github.com/D4Vinci/Scrapling)) as an automatic fallback.

---

## Why this exists

Reddit's API became paid in 2023 and has strict rate limits for registered apps. Plain HTTP requests to Reddit's HTML return `403 Forbidden`. This scraper uses Reddit's undocumented public JSON endpoints — which return full comment trees — and falls back to a stealth Chromium browser when the JSON API is unavailable.

---

## What it does

- **Posts**: fetches listing pages (hot/new/top/rising) and extracts title, score, comment count, author, domain, permalink, upvote ratio, and timestamp
- **Comments**: fetches the full comment thread (200+ comments) via the JSON API and reconstructs the nested reply tree recursively
- **Multi-subreddit**: scrape multiple subreddits in a single command and merge results into one output folder
- **Auto-method**: tries the JSON API first (fast, full threads), falls back to the browser if blocked
- **Export**: saves everything as JSON (nested tree) and CSV (flat with `parent_id` for relational joins)

---

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/PAMF2/reddit-scraper.git
cd reddit-scraper
pip install -r requirements.txt
scrapling install      # downloads Chromium browser (~150MB, one-time, needed only for browser fallback)
```

---

## Usage

### List hot posts from a subreddit

```bash
python main.py posts --sub MMA --sort hot --limit 25
```

Output:
```
 #   Score   Cmts  Title
------------------------------------------------------------------------------------------
 1. [  1634] [ 264]  Firas Zahabi invites Khamzat Chimaev to train with him and George
       WinterStill4472 | 2026-05-13 | streamable.com
       https://www.reddit.com/r/MMA/comments/1tc69wt/...

 2. [  1502] [ 278]  Jon Jones submits Lyoto Machida with a standing guillotine
       airplane231 | 2026-05-13 | imgur.com
       https://www.reddit.com/r/MMA/comments/1tc3j00/...
```

Saves `output/posts_MMA_<timestamp>.csv` and `.json`.

---

### Extract comments from a single post (200+ comments)

```bash
python main.py comments \
  --url "https://www.reddit.com/r/MMA/comments/1tc3j00/jon_jones_submits_lyoto_machida_with_a_standing/" \
  --max-comments 500
```

Output (indented thread view):
```
[u/Savage_Batmanuel  score:+591  2026-05-13]
  I forgot how good Lyoto was.
  >> https://www.reddit.com/r/MMA/comments/1tc3j00/comment/ollb90u/

  [u/NukeTheWhales85  score:+184  2026-05-13]
    He really was fascinating to watch in his early years. Doing something
    very different and making it work consistently against top opposition.
    >> https://www.reddit.com/r/MMA/comments/1tc3j00/comment/oln71r8/

    [u/catnipformysoul  score:+73  2026-05-13]
      "The Machida Era"
      >> https://www.reddit.com/r/MMA/comments/1tc3j00/comment/oln8kov/
```

For a post with 278 comments this returns 255 comments (the API skips deleted/removed entries).

---

### Scrape everything at once (posts + comments)

```bash
python main.py scrape \
  --sub MMA \
  --sort hot \
  --limit 10 \
  --max-comments 200
```

Iterates over the top N posts, fetches their full comment threads, prints everything, and saves:
- `output/posts_<sub>_<ts>.csv`
- `output/comments_<post_id>_<ts>.csv` (one per post)
- `output/full_<sub>_<ts>.json` (everything in one file)

---

### Scrape multiple subreddits at once

```bash
python main.py scrape \
  --subreddits MMA ufc boxing \
  --sort hot \
  --limit 5 \
  --max-comments 100
```

Scrapes each subreddit in sequence and merges all results into `output/full_MMA_ufc_boxing_<ts>.json`. Per-subreddit CSV files are saved individually.

---

## CLI reference

```
usage: main.py [-h] [--output OUTPUT] {posts,comments,scrape} ...

subcommands:
  posts      List posts from a subreddit
  comments   Scrape comments from a single post URL
  scrape     Scrape posts + their comments in one pass

options:
  --output, -o   Output directory (default: output/)

posts:
  --sub          Subreddit name          (default: MMA)
  --sort         hot|new|top|rising      (default: hot)
  --limit        Max posts to fetch      (default: 25)

comments:
  --url          Full Reddit post URL    (required)
  --max-comments Max comments to fetch   (default: 500)
  --depth        Max display depth       (default: 3)
  --method       auto|api|browser        (default: auto)

scrape:
  --sub          Subreddit name          (default: MMA, ignored if --subreddits set)
  --subreddits   One or more subreddits  (e.g. --subreddits MMA ufc boxing)
  --sort         hot|new|top|rising      (default: hot)
  --limit        Posts per subreddit     (default: 10)
  --max-comments Comments per post       (default: 200)
  --depth        Max display depth       (default: 3)
  --method       auto|api|browser        (default: auto)
```

### `--method` options

| value | behavior |
|---|---|
| `auto` | tries JSON API first; falls back to browser if API fails or returns 0 comments |
| `api` | forces JSON API only (fastest, 200+ comments, no browser needed) |
| `browser` | forces StealthyFetcher (renders the page, ~25 comments, slower) |

---

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

### full JSON structure

```json
[
  {
    "post": { "id": "t3_1tc3j00", "title": "...", "score": 1502, ... },
    "comments": [
      {
        "id": "t1_ollb90u",
        "author": "Savage_Batmanuel",
        "score": 591,
        "depth": 0,
        "body": "I forgot how good Lyoto was.",
        "created": "2026-05-13",
        "permalink": "...",
        "replies": [
          {
            "id": "t1_oln71r8",
            "author": "NukeTheWhales85",
            "depth": 1,
            "body": "He really was fascinating...",
            "replies": [...]
          }
        ]
      }
    ]
  }
]
```

---

## Code structure

```
reddit-scraper/
├── main.py                  # CLI entrypoint (argparse subcommands)
├── requirements.txt
├── scraper/
│   ├── __init__.py          # public API re-exports
│   ├── fetcher.py           # StealthyFetcher wrapper with retry logic
│   ├── reddit_api.py        # Reddit JSON API client (primary method)
│   ├── posts.py             # subreddit listing scraper -> Post dataclass
│   ├── comments.py          # comment thread scraper -> Comment tree (auto/api/browser)
│   └── export.py            # JSON / CSV / console output
└── output/                  # generated files (gitignored)
```

---

## How the scraping works

### Method 1: Reddit JSON API (default)

Reddit exposes public JSON endpoints that require no authentication and return full comment trees. Any request with a standard browser `User-Agent` returns `200 OK`:

```
GET https://www.reddit.com/r/MMA/hot.json?limit=100
GET https://www.reddit.com/r/MMA/comments/1tc3j00.json?limit=500&sort=top
```

The comments endpoint returns a two-element array: `[post_data, comment_tree]`. The comment tree is fully nested — each comment's `replies` field contains its child comments recursively. This gives 200+ comments per thread in a single request.

```python
data = fetch_json(url)
post    = data[0]["data"]["children"][0]["data"]
comments = data[1]["data"]["children"]  # recursively nested
```

### Method 2: StealthyFetcher browser (fallback)

If the JSON API returns 403 or zero comments, the scraper falls back to launching a real Chromium instance via [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright). This renders the full page, giving ~25 comments per load.

```
JSON API  →  GET reddit.com/r/MMA/comments/xxx.json  →  200 OK, 200+ comments
Browser   →  GET reddit.com/r/MMA/comments/xxx/      →  200 OK, ~25 comments (fallback)
```

### Post extraction

Reddit's new design uses Web Components. Each post is a `<shreddit-post>` custom element with all data stored as HTML attributes — no CSS parsing needed:

```html
<shreddit-post
  post-title="Jon Jones submits Lyoto Machida..."
  score="1502"
  comment-count="278"
  author="airplane231"
  permalink="/r/MMA/comments/1tc3j00/..."
  created-timestamp="2026-05-13T..."
  upvote-ratio="0.964"
  domain="imgur.com"
  post-type="link"
/>
```

### Comment tree reconstruction

The JSON API returns comments already nested. Each comment's `replies.data.children` contains child `Comment` objects. The scraper recurses this structure to build the same `Comment` tree used by the browser path.

When using the browser fallback, all `<shreddit-comment>` elements are collected flat and rebuilt into a tree using each element's `depth` attribute:

```python
stack = []
for comment in flat_comments:
    while stack and stack[-1].depth >= comment.depth:
        stack.pop()
    if stack:
        stack[-1].replies.append(comment)
    else:
        roots.append(comment)
    stack.append(comment)
```

---

## Combat sports subreddits

| subreddit | content |
|---|---|
| r/MMA | General MMA, UFC, Bellator, ONE |
| r/ufc | UFC-specific discussion |
| r/boxing | Professional boxing |
| r/bjj | Brazilian Jiu-Jitsu |
| r/wrestling | Amateur and pro wrestling |
| r/kickboxing | Kickboxing / K-1 / Glory |
| r/WMMA | Women's MMA |
| r/fightporn | Real street/amateur fights |
| r/mmamemes | Fight memes and reactions |

---

## Notes

- **Rate**: the JSON API path is fast (~1–2 seconds per thread). The browser fallback takes ~5–8 seconds per page.
- **No login**: scraping is done as an anonymous visitor. NSFW subreddits require login.
- **"load more" stubs**: Reddit's JSON API occasionally returns `"more"` stubs for very large threads (1000+ comments). These are skipped; the first 500 comments are always fetched.

---

## License

MIT
