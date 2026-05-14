"""
Reddit JSON API client — fetches posts and full comment threads without a browser.

Reddit's public JSON endpoints return 200 OK with a standard browser User-Agent
and no authentication. This gives access to full comment threads (~250+ comments
per post) vs ~25 from the page renderer.
"""
import logging
import time
import json
import re
from html import unescape
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .posts import Post
from .comments import Comment

log = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
REDDIT_BASE = "https://www.reddit.com"


def _get(url: str, retries: int = 3, wait: float = 2.0) -> dict | list:
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": _UA})
            with urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except HTTPError as e:
            if e.code == 429:
                log.warning("Rate limited, waiting %ds (attempt %d)", wait * 2, attempt)
                time.sleep(wait * 2)
            elif e.code == 403:
                raise RuntimeError(f"API returned 403 for {url}") from e
            else:
                log.warning("Attempt %d HTTP %d: %s", attempt, e.code, url)
        except URLError as e:
            log.warning("Attempt %d URLError: %s", attempt, e)
        if attempt < retries:
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def _clean_body(text: str) -> str:
    """Normalize Reddit markdown body text to a clean single-line string."""
    text = unescape(text.strip())
    # strip markdown blockquote markers Reddit inserts in quoted replies
    text = re.sub(r"^&gt;[^\n]*\n?", "", text, flags=re.MULTILINE)
    # collapse all newlines to a single space — avoids multiline CSV cells
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _utc_to_date(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ── Posts ──────────────────────────────────────────────────────────────────────

def get_posts_api(subreddit: str, sort: str = "hot", limit: int = 25) -> list[Post]:
    """
    Fetch subreddit listing via the JSON API.
    Reddit's API caps at 100 per request; for limit > 100 this paginates with `after`.
    """
    posts: list[Post] = []
    after: str | None = None

    while len(posts) < limit:
        batch = min(limit - len(posts), 100)
        url = f"{REDDIT_BASE}/r/{subreddit}/{sort}.json?limit={batch}"
        if after:
            url += f"&after={after}"
        log.info("API posts: r/%s (%s) offset=%d limit=%d", subreddit, sort, len(posts), batch)

        data = _get(url)
        listing = data["data"]
        children = listing.get("children", [])

        if not children:
            break

        for child in children:
            if child.get("kind") != "t3":
                continue
            p = child["data"]
            try:
                posts.append(Post(
                    id=p.get("name", ""),
                    title=unescape(p.get("title", "")).strip(),
                    author=p.get("author", "[deleted]"),
                    score=int(p.get("score", 0)),
                    comment_count=int(p.get("num_comments", 0)),
                    domain=p.get("domain", ""),
                    permalink=REDDIT_BASE + p.get("permalink", ""),
                    content_href=p.get("url", ""),
                    post_type="self" if p.get("is_self") else "link",
                    created=_utc_to_date(p.get("created_utc", 0)),
                    upvote_ratio=float(p.get("upvote_ratio", 0)),
                    subreddit=p.get("subreddit_name_prefixed", f"r/{subreddit}"),
                ))
            except Exception as exc:
                log.warning("Skipped post: %s", exc)

            if len(posts) >= limit:
                break

        after = listing.get("after")
        if not after:
            break

    log.info("API posts: got %d posts", len(posts))
    return posts


# ── Comments ───────────────────────────────────────────────────────────────────

def _parse_comment_tree(
    children: list,
    max_total: int,
    counter: list[int],  # mutable int via list so recursion can update it
) -> list[Comment]:
    """
    Recursively parse Reddit's nested comment JSON.
    counter[0] tracks total comments collected across all depths.
    Stops when counter[0] reaches max_total.
    """
    result: list[Comment] = []

    for child in children:
        if counter[0] >= max_total:
            break

        kind = child.get("kind")
        if kind == "more":
            # "load more" stubs — would need a separate API call; skipped here
            continue
        if kind != "t1":
            continue

        d = child["data"]
        body = d.get("body", "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue

        permalink = d.get("permalink", "")
        if permalink and not permalink.startswith("http"):
            permalink = REDDIT_BASE + permalink

        comment = Comment(
            id=d.get("name", ""),
            author=d.get("author", "[deleted]"),
            score=int(d.get("score", 0)),
            depth=int(d.get("depth", 0)),
            body=_clean_body(body),
            created=_utc_to_date(d.get("created_utc", 0)),
            permalink=permalink,
        )
        counter[0] += 1
        result.append(comment)

        replies = d.get("replies", "")
        if isinstance(replies, dict) and counter[0] < max_total:
            comment.replies = _parse_comment_tree(
                replies["data"]["children"],
                max_total,
                counter,
            )

    return result


def get_comments_api(post_url: str, max_comments: int = 500) -> list[Comment]:
    """
    Fetch the full comment thread via Reddit's JSON API.
    Returns a nested Comment tree (same structure as the browser scraper).
    max_comments caps the TOTAL number of comments across all depths.
    """
    url = post_url.rstrip("/")
    if not url.endswith(".json"):
        url += ".json"
    url += "?limit=500"

    log.info("API comments: %s", url)
    data = _get(url)

    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError(f"Unexpected API response shape from {url}")

    top_level_children = data[1]["data"]["children"]
    counter = [0]
    tree = _parse_comment_tree(top_level_children, max_comments, counter)

    def _total(nodes: list[Comment]) -> int:
        return sum(1 + _total(c.replies) for c in nodes)

    top = len(tree)
    total = _total(tree)
    log.info("API comments: %d top-level threads, %d total comments", top, total)
    return tree
