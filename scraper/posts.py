"""
Post listing scraper — returns hot/new/top posts from a subreddit.
"""
import logging
from dataclasses import dataclass, field
from .fetcher import fetch_page, REDDIT_BASE

log = logging.getLogger(__name__)

SORT_OPTIONS = {"hot", "new", "top", "rising"}


@dataclass
class Post:
    id: str
    title: str
    author: str
    score: int
    comment_count: int
    domain: str
    permalink: str
    content_href: str
    post_type: str
    created: str
    upvote_ratio: float
    subreddit: str


def get_posts(subreddit: str, sort: str = "hot", limit: int = 25) -> list[Post]:
    if sort not in SORT_OPTIONS:
        raise ValueError(f"sort must be one of {SORT_OPTIONS}")

    url = f"{REDDIT_BASE}/r/{subreddit}/{sort}/"
    log.info("Fetching r/%s (%s) ...", subreddit, sort)
    page = fetch_page(url)

    elements = page.css("shreddit-post")
    log.info("Found %d posts", len(elements))

    posts: list[Post] = []
    for el in elements[:limit]:
        a = el.attrib
        try:
            posts.append(Post(
                id=a.get("id", ""),
                title=a.get("post-title", "").strip(),
                author=a.get("author", ""),
                score=int(a.get("score", 0)),
                comment_count=int(a.get("comment-count", 0)),
                domain=a.get("domain", ""),
                permalink=REDDIT_BASE + a.get("permalink", ""),
                content_href=a.get("content-href", ""),
                post_type=a.get("post-type", ""),
                created=a.get("created-timestamp", "")[:10],
                upvote_ratio=float(a.get("upvote-ratio", 0)),
                subreddit=a.get("subreddit-prefixed-name", f"r/{subreddit}"),
            ))
        except Exception as exc:
            log.warning("Skipped post: %s", exc)

    return posts
