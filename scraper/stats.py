"""
Statistical analysis of scraped Reddit data.

analyse_posts(posts)        → score distribution + upvote-ratio stats
analyse_comments(comments)  → sentiment compound distribution + depth stats
cross_analyse(full_data)    → score×sentiment, depth×sentiment, ratio×sentiment correlations
full_report(full_data)      → combined dict ready for JSON export or Rich printing
"""
from __future__ import annotations

import io
import math
import statistics
import sys
from collections import defaultdict
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
console = Console(force_terminal=True, file=_stdout_utf8)


# ── helpers ───────────────────────────────────────────────────────────────────

def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _dist_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    return {
        "n":      len(values),
        "mean":   round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "stdev":  round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "min":    round(min(values), 3),
        "p25":    round(_percentile(values, 25), 3),
        "p75":    round(_percentile(values, 75), 3),
        "p95":    round(_percentile(values, 95), 3),
        "max":    round(max(values), 3),
    }


def _flatten_comments(comments: list, _depth: int = 0) -> list[dict]:
    rows: list[dict] = []
    for c in comments:
        rows.append({
            "author":  c.get("author", ""),
            "score":   c.get("score", 0),
            "depth":   c.get("depth", _depth),
            "body":    c.get("body", ""),
            "created": c.get("created", ""),
        })
        rows.extend(_flatten_comments(c.get("replies", []), _depth + 1))
    return rows


def _sentiment_compound(text: str) -> float:
    try:
        from .sentiment import analyze
        return analyze(text).compound
    except Exception:
        return 0.0


def _label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


# ── analysis functions ────────────────────────────────────────────────────────

def analyse_posts(posts: list[dict]) -> dict[str, Any]:
    scores   = [float(p.get("score", 0)) for p in posts]
    ratios   = [float(p.get("upvote_ratio", 0)) for p in posts if p.get("upvote_ratio")]
    cmt_cnts = [float(p.get("comment_count", 0)) for p in posts]
    return {
        "count":              len(posts),
        "score":              _dist_summary(scores),
        "upvote_ratio":       _dist_summary(ratios),
        "comment_count":      _dist_summary(cmt_cnts),
    }


def analyse_comments(comment_rows: list[dict]) -> dict[str, Any]:
    if not comment_rows:
        return {}

    compounds = [_sentiment_compound(r["body"]) for r in comment_rows if r.get("body")]
    scores    = [float(r.get("score", 0)) for r in comment_rows]
    depths    = [int(r.get("depth", 0))   for r in comment_rows]

    dist = {"positive": 0, "negative": 0, "neutral": 0}
    for c in compounds:
        dist[_label(c)] += 1

    return {
        "count":              len(comment_rows),
        "sentiment_compound": _dist_summary(compounds),
        "sentiment_dist":     dist,
        "score":              _dist_summary(scores),
        "depth":              _dist_summary(depths),
    }


def cross_analyse(full_data: list[dict]) -> dict[str, Any]:
    """
    Cross-information patterns from full scrape data.

    Returns:
      score_tier_sentiment   — avg compound by post score tier
      depth_sentiment        — avg compound per comment depth (0-4+)
      upvote_ratio_sentiment — avg compound bucketed by upvote ratio
      top_author_activity    — comment count per author (top 10)
    """
    # Collect per-entry stats
    score_tier_buckets: dict[str, list[float]] = defaultdict(list)
    depth_buckets:      dict[str, list[float]] = defaultdict(list)
    ratio_buckets:      dict[str, list[float]] = defaultdict(list)
    author_counts:      dict[str, int]         = defaultdict(int)

    for entry in full_data:
        post  = entry.get("post", {})
        score = float(post.get("score", 0))
        ratio = float(post.get("upvote_ratio", 0))

        if score > 1000:
            tier = ">1000"
        elif score > 500:
            tier = "501-1000"
        elif score > 100:
            tier = "101-500"
        else:
            tier = "0-100"

        if ratio >= 0.90:
            ratio_band = "≥90%"
        elif ratio >= 0.75:
            ratio_band = "75-89%"
        else:
            ratio_band = "<75%"

        rows = _flatten_comments(entry.get("comments", []))
        for r in rows:
            if not r.get("body"):
                continue
            c = _sentiment_compound(r["body"])
            score_tier_buckets[tier].append(c)

            depth = min(int(r.get("depth", 0)), 4)
            depth_buckets[str(depth)].append(c)

            ratio_buckets[ratio_band].append(c)

            author = r.get("author", "")
            if author and author not in ("[deleted]",):
                author_counts[author] += 1

    def _avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    score_tier_sentiment = {
        tier: {"avg_compound": _avg(vals), "n": len(vals)}
        for tier, vals in sorted(score_tier_buckets.items())
    }

    depth_sentiment = {
        f"depth_{d}": {"avg_compound": _avg(vals), "n": len(vals)}
        for d, vals in sorted(depth_buckets.items(), key=lambda x: int(x[0]))
    }

    ratio_sentiment = {
        band: {"avg_compound": _avg(vals), "n": len(vals)}
        for band, vals in ratio_buckets.items()
    }

    top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "score_tier_sentiment":   score_tier_sentiment,
        "depth_sentiment":        depth_sentiment,
        "upvote_ratio_sentiment": ratio_sentiment,
        "top_authors":            [{"author": a, "comments": n} for a, n in top_authors],
    }


def full_report(full_data: list[dict]) -> dict[str, Any]:
    all_posts    = [e["post"] for e in full_data if e.get("post")]
    all_comments = []
    for e in full_data:
        all_comments.extend(_flatten_comments(e.get("comments", [])))

    return {
        "posts":    analyse_posts(all_posts),
        "comments": analyse_comments(all_comments),
        "cross":    cross_analyse(full_data),
    }


# ── Rich display ──────────────────────────────────────────────────────────────

def _bar(value: float, lo: float = -1.0, hi: float = 1.0, width: int = 12) -> Text:
    norm = (value - lo) / (hi - lo)
    norm = max(0.0, min(1.0, norm))
    filled = round(norm * width)
    color  = "green" if value > 0.05 else ("red" if value < -0.05 else "dim white")
    return Text("▰" * filled + "▱" * (width - filled), style=color)


def print_report(report: dict) -> None:
    posts    = report.get("posts", {})
    comments = report.get("comments", {})
    cross    = report.get("cross", {})

    # ── Post score distribution
    ps = posts.get("score", {})
    if ps:
        table = Table(title="Post Score Distribution", box=box.SIMPLE,
                      header_style="bold dim", show_header=True)
        table.add_column("Stat",   style="dim", no_wrap=True)
        table.add_column("Value",  justify="right")
        for k in ("n", "mean", "median", "stdev", "p25", "p75", "p95", "max"):
            table.add_row(k, str(ps.get(k, "")))
        console.print(table)

    # ── Comment sentiment compound distribution
    cs = comments.get("sentiment_compound", {})
    sd = comments.get("sentiment_dist", {})
    if cs:
        avg = cs.get("mean", 0.0)
        bar = _bar(avg)
        pos = sd.get("positive", 0)
        neg = sd.get("negative", 0)
        neu = sd.get("neutral",  0)
        total = pos + neg + neu or 1

        content = Text()
        content.append("POSITIVE  ", style="bold")
        content.append_text(bar)
        content.append(f"  avg {avg:+.3f}\n", style="green" if avg > 0 else "red")
        content.append(
            f"{pos} positive ({100*pos//total}%)  ·  "
            f"{neg} negative ({100*neg//total}%)  ·  "
            f"{neu} neutral ({100*neu//total}%)\n",
            style="dim",
        )
        content.append(f"stdev {cs.get('stdev', 0.0):.3f}  ·  p25 {cs.get('p25', 0.0):+.3f}  ·  p75 {cs.get('p75', 0.0):+.3f}", style="dim")
        console.print(Panel(content, title=f"Comment Sentiment  [dim]n={cs.get('n',0)}[/dim]",
                            border_style="dim", expand=False))

    # ── Cross: score tier × sentiment
    sts = cross.get("score_tier_sentiment", {})
    if sts:
        table = Table(title="Sentiment by Post Score Tier", box=box.SIMPLE,
                      header_style="bold dim", show_header=True)
        table.add_column("Score tier", no_wrap=True)
        table.add_column("Comments",   justify="right", style="dim")
        table.add_column("Avg compound", justify="right")
        table.add_column("",           no_wrap=True)
        for tier, v in sts.items():
            avg = v["avg_compound"]
            color = "green" if avg > 0.05 else ("red" if avg < -0.05 else "dim white")
            table.add_row(tier, str(v["n"]), Text(f"{avg:+.3f}", style=color), _bar(avg))
        console.print(table)

    # ── Cross: depth × sentiment
    ds = cross.get("depth_sentiment", {})
    if ds:
        table = Table(title="Sentiment by Comment Depth", box=box.SIMPLE,
                      header_style="bold dim", show_header=True)
        table.add_column("Depth",       no_wrap=True)
        table.add_column("Comments",    justify="right", style="dim")
        table.add_column("Avg compound", justify="right")
        table.add_column("",            no_wrap=True)
        for depth_key, v in ds.items():
            label = depth_key.replace("depth_", "")
            avg = v["avg_compound"]
            suffix = "+" if int(label) >= 4 else ""
            color = "green" if avg > 0.05 else ("red" if avg < -0.05 else "dim white")
            table.add_row(f"depth {label}{suffix}", str(v["n"]),
                          Text(f"{avg:+.3f}", style=color), _bar(avg))
        console.print(table)

    # ── Cross: upvote ratio × sentiment
    rs = cross.get("upvote_ratio_sentiment", {})
    if rs:
        table = Table(title="Sentiment by Upvote Ratio", box=box.SIMPLE,
                      header_style="bold dim", show_header=True)
        table.add_column("Ratio band",  no_wrap=True)
        table.add_column("Comments",    justify="right", style="dim")
        table.add_column("Avg compound", justify="right")
        table.add_column("",            no_wrap=True)
        for band, v in sorted(rs.items(), reverse=True):
            avg = v["avg_compound"]
            color = "green" if avg > 0.05 else ("red" if avg < -0.05 else "dim white")
            table.add_row(band, str(v["n"]), Text(f"{avg:+.3f}", style=color), _bar(avg))
        console.print(table)

    # ── Top authors
    authors = cross.get("top_authors", [])
    if authors:
        table = Table(title="Most Active Commenters", box=box.SIMPLE,
                      header_style="bold dim", show_header=True)
        table.add_column("#",        justify="right", style="dim")
        table.add_column("Author",   no_wrap=True)
        table.add_column("Comments", justify="right")
        for i, row in enumerate(authors, 1):
            table.add_row(str(i), f"u/{row['author']}", str(row["comments"]))
        console.print(table)
