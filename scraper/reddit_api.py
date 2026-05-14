"""
Reddit JSON API client — fetches posts and full comment threads without a browser.

Reddit's public JSON endpoints return 200 OK with a standard browser User-Agent
and no authentication, giving access to full comment threads (vs ~25 from page render).
"""
import logging
import time
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .posts import Post
from .comments import Comment

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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


def _utc_to_date(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def get_posts_api(subreddit: str, sort: str = "hot", limit: int = 25) -> list[Post]:
    url = f"{REDDIT_BASE}/r/{subreddit}/{sort}.json?limit={min(limit, 100)}"
    log.info("API: fetching r/%s (%s) limit=%d", subreddit, sort, limit)
    data = _get(url)

    posts: list[Post] = []
    for child in data["data"]["children"]:
        if child.get("kind") != "t3":
            continue
        p = child["data"]
        try:
            post_type = "self" if p.get("is_self") else "link"
            posts.append(Post(
                id=p.get("name", ""),
                title=p.get("title", "").strip(),
                author=p.get("author", "[deleted]"),
                score=int(p.get("score", 0)),
                comment_count=int(p.get("num_comments", 0)),
                domain=p.get("domain", ""),
                permalink=REDDIT_BASE + p.get("permalink", ""),
                content_href=p.get("url", ""),
                post_type=post_type,
                created=_utc_to_date(p.get("created_utc", 0)),
                upvote_ratio=float(p.get("upvote_ratio", 0)),
                subreddit=p.get("subreddit_name_prefixed", f"r/{subreddit}"),
            ))
        except Exception as exc:
            log.warning("Skipped post: %s", exc)

        if len(posts) >= limit:
            break

    log.info("API: got %d posts", len(posts))
    return posts


def _parse_comment_tree(children: list, max_comments: int, collected: list[Comment]) -> None:
    """Recursively parse Reddit's nested comment JSON into Comment objects."""
    for child in children:
        if len(collected) >= max_comments:
            return
        kind = child.get("kind")
        if kind == "more":
            # "load more" stubs — skipped (would need another API call per stub)
            continue
        if kind != "t1":
            continue

        d = child["data"]
        body = d.get("body", "").strip()
        if not body or body == "[deleted]" or body == "[removed]":
            continue

        permalink = d.get("permalink", "")
        if permalink and not permalink.startswith("http"):
            permalink = REDDIT_BASE + permalink

        comment = Comment(
            id=d.get("name", ""),
            author=d.get("author", "[deleted]"),
            score=int(d.get("score", 0)),
            depth=int(d.get("depth", 0)),
            body=body,
            created=_utc_to_date(d.get("created_utc", 0)),
            permalink=permalink,
        )
        collected.append(comment)

        replies = d.get("replies", "")
        if isinstance(replies, dict):
            reply_children = replies["data"]["children"]
            child_comments: list[Comment] = []
            _parse_comment_tree(reply_children, max_comments - len(collected), child_comments)
            comment.replies = child_comments


def get_comments_api(post_url: str, max_comments: int = 500) -> list[Comment]:
    """
    Fetch full comment thread via Reddit's JSON API.

    post_url can be a full URL like https://www.reddit.com/r/MMA/comments/abc123/title/
    or just the path. Returns a nested Comment tree, same as the browser scraper.
    """
    url = post_url.rstrip("/")
    if not url.endswith(".json"):
        url += ".json"
    if "?" not in url:
        url += f"?limit=500&sort=top"
    else:
        url += f"&limit=500&sort=top"

    log.info("API: fetching comments from %s", url)
    data = _get(url)

    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError(f"Unexpected API response shape from {url}")

    top_level_children = data[1]["data"]["children"]
    collected: list[Comment] = []
    _parse_comment_tree(top_level_children, max_comments, collected)

    log.info("API: collected %d comments", len(collected))

    roots = [c for c in collected if c.depth == 0]
    return roots
