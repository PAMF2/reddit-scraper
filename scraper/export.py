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
from .display import (
    print_posts,
    print_comments,
    print_thread_sentiment,
    print_notable,
    print_news_post,
    print_save,
)

__all__ = [
    "print_posts",
    "print_comments",
    "print_thread_sentiment",
    "print_notable",
    "print_news_post",
    "print_save",
    "save_json",
    "save_posts_csv",
    "save_comments_csv",
]


# ── JSON ──────────────────────────────────────────────────────────────────────

def _comment_to_dict(c: Comment) -> dict:
    d = dataclasses.asdict(c)
    d["replies"] = [_comment_to_dict(r) for r in c.replies]
    return d


def save_json(data: dict | list, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print_save(path)


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
    print_save(path)


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
    print_save(path)
