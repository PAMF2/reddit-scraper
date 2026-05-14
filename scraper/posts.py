"""
Post listing — returns hot/new/top/rising posts from a subreddit.
method="auto"    tries JSON API first, falls back to browser
method="api"     JSON API only (fast, supports >100 posts via pagination)
method="browser" StealthyFetcher only (capped at ~27 posts per page)
"""
import logging
from dataclasses import dataclass
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


def _get_posts_browser(subreddit: str, sort: str, limit: int) -> list[Post]:
    url = f"{REDDIT_BASE}/r/{subreddit}/{sort}/"
    log.info("Browser posts: r/%s (%s)", subreddit, sort)
    page = fetch_page(url)
    elements = page.css("shreddit-post")
    log.info("Browser posts: found %d elements", len(elements))

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
                domain=("self" if (a.get("domain", "") or "").startswith("self.") else a.get("domain", "")),
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


def get_posts(
    subreddit: str,
    sort: str = "hot",
    limit: int = 25,
    method: str = "auto",
) -> list[Post]:
    if sort not in SORT_OPTIONS:
        raise ValueError(f"sort must be one of {SORT_OPTIONS}")
    if method not in ("auto", "api", "browser"):
        raise ValueError(f"method must be 'auto', 'api', or 'browser'")

    if method == "browser":
        return _get_posts_browser(subreddit, sort, limit)

    try:
        from .reddit_api import get_posts_api
        posts = get_posts_api(subreddit, sort=sort, limit=limit)
        if posts:
            return posts
        log.warning("API returned 0 posts, falling back to browser")
    except Exception as exc:
        if method == "api":
            raise
        log.warning("API failed (%s), falling back to browser", exc)

    return _get_posts_browser(subreddit, sort, limit)
