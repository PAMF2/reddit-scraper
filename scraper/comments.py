"""
Comment scraper — extracts top-level and threaded comments from a post URL.
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
    stack: list[Comment] = []  # stack of ancestors by depth

    for c in flat:
        while stack and stack[-1].depth >= c.depth:
            stack.pop()
        if stack:
            stack[-1].replies.append(c)
        else:
            roots.append(c)
        stack.append(c)

    return roots


def get_comments(
    post_url: str,
    max_comments: int = 100,
    nest: bool = True,
) -> list[Comment]:
    log.info("Fetching comments for %s", post_url)
    page = fetch_page(post_url)

    elements = page.css("shreddit-comment")
    log.info("Found %d comment elements", len(elements))

    flat: list[Comment] = []
    for el in elements[:max_comments]:
        c = _parse_comment(el)
        if c and c.body:
            flat.append(c)

    return _build_tree(flat) if nest else flat
