"""
Comment scraper — extracts top-level and threaded comments from a post URL.

Method selection:
  "auto"    — tries JSON API first, falls back to browser if it fails
  "api"     — forces Reddit JSON API (fast, no browser needed)
  "browser" — forces StealthyFetcher (slow, renders full page)
"""
import logging
from dataclasses import dataclass, field
from .fetcher import fetch_page

log = logging.getLogger(__name__)


@dataclass
class Comment:
    id: str
    author: str
    score: int
    depth: int
    body: str
    created: str
    permalink: str
    replies: list["Comment"] = field(default_factory=list)


def _parse_comment(el) -> Comment | None:
    a = el.attrib
    thingid = a.get("thingid", "")
    if not thingid:
        return None

    body_id = f"{thingid}-comment-rtjson-content"
    texts = el.css(f"#{body_id} p::text").getall()
    body = " ".join(t.strip() for t in texts if t.strip())

    return Comment(
        id=thingid,
        author=a.get("author", "[deleted]"),
        score=int(a.get("score", 0)),
        depth=int(a.get("depth", 0)),
        body=body,
        created=a.get("created", "")[:10],
        permalink="https://www.reddit.com" + a.get("permalink", ""),
    )


def _build_tree(flat: list[Comment]) -> list[Comment]:
    """Convert flat depth-ordered list into a nested tree."""
    if not flat:
        return []

    roots: list[Comment] = []
    stack: list[Comment] = []

    for c in flat:
        while stack and stack[-1].depth >= c.depth:
            stack.pop()
        if stack:
            stack[-1].replies.append(c)
        else:
            roots.append(c)
        stack.append(c)

    return roots


def _get_comments_browser(post_url: str, max_comments: int) -> list[Comment]:
    page = fetch_page(post_url)
    elements = page.css("shreddit-comment")
    log.info("Browser: found %d comment elements", len(elements))

    flat: list[Comment] = []
    for el in elements[:max_comments]:
        c = _parse_comment(el)
        if c and c.body:
            flat.append(c)

    return _build_tree(flat)


def get_comments(
    post_url: str,
    max_comments: int = 500,
    nest: bool = True,
    method: str = "auto",
) -> list[Comment]:
    """
    Fetch comments for a Reddit post.

    method="auto"    tries API first, falls back to browser
    method="api"     Reddit JSON API only (fast, 200+ comments)
    method="browser" StealthyFetcher only (slow, ~25 comments)
    """
    if method not in ("auto", "api", "browser"):
        raise ValueError(f"method must be 'auto', 'api', or 'browser'; got {method!r}")

    if method == "browser":
        return _get_comments_browser(post_url, max_comments)

    # Try the JSON API path
    try:
        from .reddit_api import get_comments_api
        comments = get_comments_api(post_url, max_comments=max_comments)
        if comments:
            return comments
        log.warning("API returned 0 comments, falling back to browser")
    except Exception as exc:
        if method == "api":
            raise
        log.warning("API failed (%s), falling back to browser", exc)

    if method == "auto":
        return _get_comments_browser(post_url, max_comments)

    return []
