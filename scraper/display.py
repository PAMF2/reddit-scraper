import sys
import io
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

_stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
console = Console(force_terminal=True, file=_stdout_utf8)

_TAG_COLORS = {
    "news":   "cyan",
    "result": "yellow",
    "leak":   "red",
    "hype":   "magenta",
}


def _tag_pills(categories: list[str]) -> Text:
    t = Text()
    for i, cat in enumerate(categories):
        color = _TAG_COLORS.get(cat, "white")
        t.append(f"[{cat.upper()}]", style=f"bold {color}")
        if i < len(categories) - 1:
            t.append(" ")
    return t


def _score_color(score: int) -> str:
    if score > 500:
        return "green"
    if score > 100:
        return "yellow"
    return "white"


def print_posts(posts, show_tags: bool = False) -> None:
    from .news import tag_text

    if not posts:
        console.print("[dim]No posts found.[/dim]")
        return

    sub = posts[0].subreddit if posts else "?"
    console.print()
    console.print(Panel(
        f"[bold]{sub}[/bold]  ·  [dim]{len(posts)} posts[/dim]",
        expand=False,
        border_style="dim",
    ))

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", expand=False)
    table.add_column("#", justify="right", style="dim", no_wrap=True)
    table.add_column("Score", justify="right", no_wrap=True)
    table.add_column("Cmts", justify="right", style="dim", no_wrap=True)
    table.add_column("Title", justify="left", max_width=55)
    if show_tags:
        table.add_column("Tags", justify="left", no_wrap=True)
    table.add_column("Author", justify="right", style="dim", no_wrap=True, max_width=20)
    table.add_column("Date", justify="right", style="dim", no_wrap=True)

    for i, p in enumerate(posts, 1):
        score_text = Text(f"{p.score:,}", style=_score_color(p.score))
        title_text = Text(p.title[:60] + ("…" if len(p.title) > 60 else ""), style="bold white")
        row = [str(i), score_text, str(p.comment_count), title_text]
        if show_tags:
            tag = tag_text(p.title)
            row.append(_tag_pills(tag.categories) if tag.any else Text(""))
        row += [p.author, p.created]
        table.add_row(*row)

    console.print(table)


def _sentiment_dot(label: str) -> Text:
    if label == "positive":
        return Text("●", style="green")
    if label == "negative":
        return Text("●", style="red")
    return Text("○", style="dim white")


def print_comments(comments, max_depth: int = 3, with_sentiment: bool = False) -> None:
    from .sentiment import analyze as _analyze

    def _render(c, indent: int = 0) -> None:
        if indent > max_depth:
            return
        pad = "  " * indent

        if with_sentiment:
            s = _analyze(c.body)
            dot = _sentiment_dot(s.label)
            sent_color = "green" if s.label == "positive" else ("red" if s.label == "negative" else "dim white")
            header = Text()
            header.append(pad)
            header.append_text(dot)
            header.append(f" u/{c.author}", style="bold")
            header.append(f"  +{c.score}", style="dim")
            header.append(f"  {c.created}", style="dim")
            header.append(f"   ▲ {s.compound:+.2f}", style=sent_color)
        else:
            header = Text()
            header.append(pad)
            header.append(f"u/{c.author}", style="bold")
            header.append(f"  +{c.score}", style="dim")
            header.append(f"  {c.created}", style="dim")

        console.print(header)

        body_pad = pad + "  "
        console.print(Text(body_pad + c.body, style="white"), soft_wrap=True)
        console.print()

        for r in c.replies:
            _render(r, indent + 1)

    for c in comments:
        _render(c)


def print_thread_sentiment(agg: dict) -> None:
    if not agg or agg.get("total", 0) == 0:
        return

    avg = agg.get("avg_compound", 0.0)
    dist = agg.get("distribution", {})
    pos = dist.get("positive", 0)
    neg = dist.get("negative", 0)
    neu = dist.get("neutral", 0)

    filled = round((avg + 1) / 2 * 10)
    filled = max(0, min(10, filled))
    bar = "▰" * filled + "▱" * (10 - filled)

    avg_color = "green" if avg > 0 else ("red" if avg < 0 else "dim white")
    avg_str = f"{avg:+.2f}"

    content = Text()
    content.append("POSITIVE  ", style="bold")
    content.append(bar, style=avg_color)
    content.append(f"  avg {avg_str}", style=avg_color)
    content.append(f"\n{pos} positive  ·  {neg} negative  ·  {neu} neutral", style="dim")

    console.print(Panel(content, title="Thread Sentiment", border_style="dim", expand=False))


def print_notable(notable: list[dict]) -> None:
    if not notable:
        return

    table = Table(title="Notable Comments", box=box.SIMPLE, show_header=True, header_style="bold dim", expand=False)
    table.add_column("Category", style="bold", no_wrap=True)
    table.add_column("Author", no_wrap=True, max_width=22)
    table.add_column("Score", justify="right", no_wrap=True)
    table.add_column("Body", max_width=60)

    for n in notable[:10]:
        cats = "/".join(n["categories"]).upper()
        cat_color = _TAG_COLORS.get(n["categories"][0], "white") if n["categories"] else "white"
        body_preview = n["body"][:100] + ("…" if len(n["body"]) > 100 else "")
        table.add_row(
            Text(cats, style=f"bold {cat_color}"),
            f"u/{n['author']}",
            f"+{n['score']}",
            body_preview,
        )

    console.print(table)


def print_news_post(post, tag) -> None:
    from .news import NewsTag

    if not isinstance(tag, NewsTag):
        return

    cats = tag.categories
    primary = cats[0] if cats else "news"
    color = _TAG_COLORS.get(primary, "cyan")
    label = "/".join(c.upper() for c in cats)

    meta = Text()
    meta.append(f"▲ {post.score:,}", style="green" if post.score > 500 else "yellow")
    meta.append(f"  •  {post.comment_count} comments", style="dim")
    meta.append(f"  •  u/{post.author}", style="dim")
    meta.append(f"  •  {post.created}", style="dim")

    content = Text()
    content.append(post.title + "\n", style="bold white")
    content.append_text(meta)

    domain = post.domain or ""
    if domain and domain != "self":
        content.append(f"\nSource: {domain}", style="dim cyan")

    console.print(Panel(content, title=f"[bold {color}][{label}][/bold {color}]", border_style=color))


def print_save(path) -> None:
    console.print(f"  [dim]saved[/dim] {path}")


def print_news_header(subreddits: list[str], sort: str) -> None:
    from datetime import date
    today = date.today().strftime("%d %b %Y")
    subs = " ".join(f"r/{s}" for s in subreddits)
    console.print()
    console.print(Panel(
        f"[bold]Breaking news scan[/bold]  ·  [dim]{subs}[/dim]  ·  [dim]{sort}[/dim]  ·  [dim]{today}[/dim]",
        expand=False,
        border_style="dim",
    ))
