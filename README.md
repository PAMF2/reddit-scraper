# reddit-scraper

A Python scraper for Reddit that extracts posts and threaded comments from any subreddit — built specifically for combat sports analysis (MMA, boxing, BJJ, etc.).

Uses [Scrapling](https://github.com/D4Vinci/Scrapling) with a stealth headless browser to bypass Reddit's bot protection and extract structured data without the official API.

---

## Why this exists

Reddit's API became paid in 2023 and has strict rate limits. Plain HTTP requests to Reddit return `403 Forbidden`. This scraper uses a stealth Chromium browser that mimics real user behaviour, bypassing Reddit's anti-bot layer and returning `200 OK` consistently.

---

## What it does

- **Posts**: scrapes listing pages (hot/new/top/rising) and extracts title, score, comment count, author, domain, permalink, upvote ratio, and timestamp — all from `<shreddit-post>` element attributes
- **Comments**: navigates to each post, extracts every comment with its body text, author, score, depth, and permalink — then reconstructs the full nested thread tree
- **Export**: saves everything as JSON (nested tree) and CSV (flat with `parent_id` for relational joins)

---

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/PAMF2/reddit-scraper.git
cd reddit-scraper
pip install -r requirements.txt
scrapling install      # downloads Chromium browser (~150MB, one-time)
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

### Extract comments from a single post

```bash
python main.py comments \
  --url "https://www.reddit.com/r/MMA/comments/1tc3j00/jon_jones_submits_lyoto_machida_with_a_standing/" \
  --max-comments 100 \
  --depth 3
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

Saves `output/comments_<slug>_<timestamp>.csv` and `.json`.

---

### Scrape everything at once (posts + comments)

```bash
python main.py scrape \
  --sub MMA \
  --sort hot \
  --limit 10 \
  --max-comments 100 \
  --depth 3
```

Iterates over the top N posts, fetches their comments, prints everything, and saves:
- `output/posts_<sub>_<ts>.csv`
- `output/comments_<post_id>_<ts>.csv` (one per post)
- `output/full_<sub>_<ts>.json` (everything in one file)

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
  --max-comments Max comments to fetch   (default: 100)
  --depth        Max display depth       (default: 3)

scrape:
  --sub          Subreddit name          (default: MMA)
  --sort         hot|new|top|rising      (default: hot)
  --limit        Posts to scrape         (default: 10)
  --max-comments Comments per post       (default: 50)
  --depth        Max display depth       (default: 3)
```

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
│   ├── posts.py             # subreddit listing scraper -> Post dataclass
│   ├── comments.py          # comment thread scraper -> Comment tree
│   └── export.py            # JSON / CSV / console output
└── output/                  # generated files (gitignored)
```

---

## How the scraping works

### Why StealthyFetcher (not plain HTTP)

Reddit returns `403 Forbidden` to any request that doesn't look like a real browser. `StealthyFetcher` launches a real Chromium instance with patched fingerprints (via [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright)) — this gets `200 OK` every time.

```
Plain Fetcher  →  GET reddit.com  →  403 Forbidden
StealthyFetcher →  GET reddit.com  →  200 OK ✓
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

### Comment extraction — the nesting problem

Reddit renders all comments in a flat DOM sequence (not a true tree), and each `<shreddit-comment>` contains its children inside itself. A naive `p::text` selector on a parent comment returns ALL paragraph text from all descendant comments too.

**Solution**: each comment has a `thingid` attribute (e.g., `t1_ollb90u`). Reddit generates a unique `div` ID for each comment's body: `t1_ollb90u-comment-rtjson-content`. Selecting paragraphs inside that specific div returns only that comment's own text:

```python
thingid  = el.attrib.get("thingid")          # "t1_ollb90u"
body_div = f"{thingid}-comment-rtjson-content"
body     = el.css(f"#{body_div} p::text").getall()
```

### Thread tree reconstruction

All `<shreddit-comment>` elements are collected flat, then rebuilt into a tree using each element's `depth` attribute (0 = top-level, 1 = reply, 2 = reply to reply, etc.):

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

## Limitations

- **Comments per page**: Reddit renders ~25 comments per page load. Increasing `--max-comments` beyond ~25 may not capture more without scroll/pagination (not yet implemented).
- **Rate**: each page fetch takes ~5–8 seconds (real browser). Scraping 10 posts with 50 comments each takes roughly 2–3 minutes.
- **Dynamic content**: comments loaded via "load more" buttons are not fetched in this version.
- **No login**: scraping is done as an anonymous visitor. NSFW subreddits require login.

---

## License

MIT
