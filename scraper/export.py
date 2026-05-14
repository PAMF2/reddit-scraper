"""
Export scraped data to JSON, CSV, or pretty-printed console output.
Sentiment columns are included in CSVs when sentiment analysis is enabled.
"""
import json
import csv
import dataclasses
from pathlib import Path
from .posts import Post
from .comments import Comment


# ── JSON ──────────────────────────────────────────────────────────────────────

def _comment_to_dict(c: Comment) -> dict:
    d = dataclasses.asdict(c)
    d["replies"] = [_comment_to_dict(r) for r in c.replies]
    return d


def save_json(data: dict | list, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[saved] {path}")


# ── CSV ───────────────────────────────────────────────────────────────────────

def _flatten_comments(
    comments: list[Comment],
    post_id: str = "",
    with_sentiment: bool = False,
) -> list[dict]:
    from .sentiment import analyze as _analyze

    rows = []

    def walk(c: Comment, parent_id: str = "") -> None:
        row: dict = {
            "post_id": post_id,
            "comment_id": c.id,
            "parent_id": parent_id,
            "depth": c.depth,
            "author": c.author,
            "score": c.score,
            "created": c.created,
            "body": c.body,
            "permalink": c.permalink,
        }
        if with_sentiment:
            s = _analyze(c.body)
            row["sentiment"] = s.label
            row["sentiment_compound"] = s.compound
            row["sentiment_intensity"] = s.intensity
        rows.append(row)
        for r in c.replies:
            walk(r, c.id)

    for c in comments:
        walk(c)
    return rows


def save_posts_csv(posts: list[Post], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not posts:
        return
    fields = list(dataclasses.asdict(posts[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in posts:
            w.writerow(dataclasses.asdict(p))
    print(f"[saved] {path}")


def save_comments_csv(
    comments: list[Comment],
    path: str | Path,
    post_id: str = "",
    with_sentiment: bool = False,
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rows = _flatten_comments(comments, post_id, with_sentiment=with_sentiment)
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[saved] {path}")


# ── Console pretty-print ──────────────────────────────────────────────────────

def _p(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"), **kwargs)


_SENT_ICON = {
    "positive": "(+)",
    "negative": "(-)",
    "neutral":  "( )",
}


def print_posts(posts: list[Post], show_tags: bool = False) -> None:
    from .news import tag_text

    _p(f"\n{'#':>2}  {'Score':>6}  {'Cmts':>5}  Title")
    _p("-" * 90)
    for i, p in enumerate(posts, 1):
        tag_str = ""
        if show_tags:
            tag = tag_text(p.title)
            if tag.any:
                tag_str = "  [" + "/".join(tag.categories).upper() + "]"
        _p(f"{i:>2}. [{p.score:>6}] [{p.comment_count:>4}]  {p.title[:65]}{tag_str}")
        _p(f"      {p.author} | {p.created} | {p.domain}")
        _p(f"      {p.permalink}")
        _p()


def print_comments(
    comments: list[Comment],
    max_depth: int = 3,
    with_sentiment: bool = False,
) -> None:
    from .sentiment import analyze as _analyze

    def _print(c: Comment, indent: int = 0) -> None:
        if indent > max_depth:
            return
        pad = "  " * indent
        sent_str = ""
        if with_sentiment:
            s = _analyze(c.body)
            sent_str = f"  {_SENT_ICON.get(s.label, '')} {s.compound:+.2f}"
        _p(f"{pad}[u/{c.author}  score:{c.score:+}  {c.created}{sent_str}]")
        for line in c.body.split(". "):
            if line.strip():
                _p(f"{pad}  {line.strip()}")
        _p(f"{pad}  >> {c.permalink}")
        _p()
        for r in c.replies:
            _print(r, indent + 1)

    for c in comments:
        _print(c)
