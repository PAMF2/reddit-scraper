"""
News and leak detector — filters posts and comments for breaking news,
fight results, leaks, and official announcements.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .posts import Post

# ── Keyword banks ─────────────────────────────────────────────────────────────

_NEWS_KEYWORDS = re.compile(
    r"\b("
    r"breaking|exclusive|confirmed|report|sources?|leaked?|rumou?r|"
    r"announced?|official|signing|contract|released?|cut|fired|"
    r"postponed?|cancelled?|delayed?|rescheduled?|pulled?|withdrawn?|"
    r"injured?|injury|surgery|hospitali[sz]ed?|retired?|retirement|"
    r"stripped|stripped of|vacated?|champion|title shot|"
    r"drug test|failed test|suspension|ban|usada|vada|wada|doping|ped"
    r")\b",
    re.IGNORECASE,
)

_RESULT_KEYWORDS = re.compile(
    r"\b("
    r"ko|tko|knockout|submission|sub|choke|armbar|heel hook|triangle|"
    r"guillotine|rear.naked|decision|split decision|unanimous|majority|"
    r"disqualif|dq|no contest|nc|draw|stoppage|finish|finished|"
    r"round \d|first round|second round|third round|fourth round|fifth round|"
    r"belt|champion|new champion|new ufc|new bellator|new one|new pfl"
    r")\b",
    re.IGNORECASE,
)

_LEAK_KEYWORDS = re.compile(
    r"\b("
    r"leaked?|insider|source says?|i heard|reportedly|apparently|"
    r"exclusive|behind the scenes|off the record|dm|dmed|"
    r"whispers?|word is|word on the street|rumou?red?"
    r")\b",
    re.IGNORECASE,
)

_HYPE_KEYWORDS = re.compile(
    r"\b("
    r"fight of the (year|night|decade|century)|foty|fotn|potn|kotn|sotn|"
    r"best fight|greatest fight|most exciting|legendary|iconic|historic|"
    r"goat|greatest of all time|all.time great"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class NewsTag:
    is_news: bool = False
    is_result: bool = False
    is_leak: bool = False
    is_hype: bool = False
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return self.is_news or self.is_result or self.is_leak or self.is_hype

    @property
    def categories(self) -> list[str]:
        cats = []
        if self.is_news:
            cats.append("news")
        if self.is_result:
            cats.append("result")
        if self.is_leak:
            cats.append("leak")
        if self.is_hype:
            cats.append("hype")
        return cats


_OFFICIAL_THREAD = re.compile(r"^\[OFFICIAL\]", re.IGNORECASE)


def tag_text(text: str) -> NewsTag:
    """Return a NewsTag describing what kind of notable content this text contains."""
    tag = NewsTag()
    if not text:
        return tag

    if _OFFICIAL_THREAD.match(text):
        return tag

    for m in _NEWS_KEYWORDS.finditer(text):
        tag.is_news = True
        tag.matched_keywords.append(m.group().lower())

    for m in _RESULT_KEYWORDS.finditer(text):
        tag.is_result = True
        if m.group().lower() not in tag.matched_keywords:
            tag.matched_keywords.append(m.group().lower())

    for m in _LEAK_KEYWORDS.finditer(text):
        tag.is_leak = True
        if m.group().lower() not in tag.matched_keywords:
            tag.matched_keywords.append(m.group().lower())

    for m in _HYPE_KEYWORDS.finditer(text):
        tag.is_hype = True
        if m.group().lower() not in tag.matched_keywords:
            tag.matched_keywords.append(m.group().lower())

    tag.matched_keywords = list(dict.fromkeys(tag.matched_keywords))  # dedupe, preserve order
    return tag


def filter_news_posts(posts: list[Post], categories: list[str] | None = None) -> list[Post]:
    """
    Return only posts whose title matches news/result/leak/hype keywords.
    categories: subset of ["news", "result", "leak", "hype"] to filter by.
                None = any category.
    """
    result = []
    for p in posts:
        tag = tag_text(p.title)
        if not tag.any:
            continue
        if categories:
            if not any(c in tag.categories for c in categories):
                continue
        result.append(p)
    return result


def find_notable_comments(comments: list, min_score: int = 5) -> list[dict]:
    """
    Walk a comment tree and return comments that contain notable keywords.
    Returned as flat list of dicts with comment data + tags.
    """
    from .comments import Comment

    notable = []

    def _walk(nodes: list[Comment]) -> None:
        for c in nodes:
            if c.score >= min_score:
                tag = tag_text(c.body)
                if tag.any:
                    notable.append({
                        "id": c.id,
                        "author": c.author,
                        "score": c.score,
                        "depth": c.depth,
                        "body": c.body,
                        "permalink": c.permalink,
                        "categories": tag.categories,
                        "keywords": tag.matched_keywords,
                    })
            _walk(c.replies)

    _walk(comments)
    return sorted(notable, key=lambda x: x["score"], reverse=True)
