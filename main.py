"""
reddit-scraper CLI

Commands:
  posts      List posts from a subreddit
  comments   Scrape comments from a single post URL
  scrape     Scrape posts + comments (one or multiple subreddits)
  news       Show only breaking news / leaks / results from a subreddit
  analyze    Run Claude AI analysis on a saved full_*.json file

Examples:
  python main.py posts --sub MMA --sort hot --limit 25
  python main.py comments --url https://www.reddit.com/r/MMA/comments/... --sentiment
  python main.py scrape --sub MMA --limit 10 --max-comments 200 --sentiment
  python main.py scrape --subreddits MMA ufc boxing --limit 5 --analyze
  python main.py news --subreddits MMA ufc boxing --sort new --limit 50
  python main.py analyze --file output/full_MMA_20260514.json
"""
import argparse
import logging
import os
from pathlib import Path
from datetime import datetime

import scraper

logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

METHOD_HELP = "auto (default) | api (fast, no browser) | browser (slow, ~25 results)"


# ── posts ─────────────────────────────────────────────────────────────────────

def cmd_posts(args):
    posts = scraper.get_posts(args.sub, sort=args.sort, limit=args.limit, method=args.method)
    scraper.print_posts(posts, show_tags=True)
    if args.output:
        out = Path(args.output)
        scraper.save_posts_csv(posts, out / f"posts_{args.sub}_{TIMESTAMP}.csv")
        scraper.save_json([p.__dict__ for p in posts], out / f"posts_{args.sub}_{TIMESTAMP}.json")


# ── comments ──────────────────────────────────────────────────────────────────

def cmd_comments(args):
    comments = scraper.get_comments(args.url, max_comments=args.max_comments, method=args.method)
    scraper.print_comments(comments, max_depth=args.depth, with_sentiment=args.sentiment)

    if args.sentiment:
        agg = scraper.analyze_thread(comments)
        scraper.print_thread_sentiment(agg)

    notable = scraper.find_notable_comments(comments, min_score=args.min_score)
    if notable:
        scraper.print_notable(notable)

    if args.output:
        out = Path(args.output)
        slug = args.url.rstrip("/").split("/")[-1][:40]
        scraper.save_json(
            [scraper.export._comment_to_dict(c) for c in comments],
            out / f"comments_{slug}_{TIMESTAMP}.json",
        )
        scraper.save_comments_csv(
            comments,
            out / f"comments_{slug}_{TIMESTAMP}.csv",
            with_sentiment=args.sentiment,
        )


# ── scrape ────────────────────────────────────────────────────────────────────

def _scrape_sub(sub: str, args, out: Path | None, all_data: list) -> None:
    from scraper.display import console
    posts = scraper.get_posts(sub, sort=args.sort, limit=args.limit, method=args.method)
    scraper.print_posts(posts, show_tags=True)
    if out:
        scraper.save_posts_csv(posts, out / f"posts_{sub}_{TIMESTAMP}.csv")

    for i, post in enumerate(posts, 1):
        console.rule(f"[{i}/{len(posts)}] r/{sub} — {post.title[:60]}")
        try:
            comments = scraper.get_comments(
                post.permalink,
                max_comments=args.max_comments,
                method=args.method,
            )
        except Exception as exc:
            console.print(f"  [red]ERROR:[/red] {exc}")
            continue

        scraper.print_comments(comments, max_depth=args.depth, with_sentiment=args.sentiment)

        if args.sentiment:
            agg = scraper.analyze_thread(comments)
            scraper.print_thread_sentiment(agg)

        notable = scraper.find_notable_comments(comments, min_score=5)
        if notable:
            scraper.print_notable(notable[:3])

        entry: dict = {
            "post": post.__dict__,
            "comments": [scraper.export._comment_to_dict(c) for c in comments],
        }

        if args.sentiment:
            entry["sentiment"] = scraper.analyze_thread(comments)

        if getattr(args, "analyze", False) and args.api_key:
            try:
                from scraper.analyzer import analyze_post, print_analysis
                analysis = analyze_post(
                    post.title, post.permalink, comments,
                    api_key=args.api_key,
                )
                print_analysis(analysis)
                entry["claude_analysis"] = analysis.raw
            except Exception as exc:
                console.print(f"  [red][Claude] ERROR:[/red] {exc}")

        all_data.append(entry)

        if out:
            slug = post.id or post.title[:20].replace(" ", "_")
            scraper.save_comments_csv(
                comments,
                out / f"comments_{slug}_{TIMESTAMP}.csv",
                post.id,
                with_sentiment=args.sentiment,
            )


def cmd_scrape(args):
    from scraper.display import console
    subreddits = args.subreddits if args.subreddits else [args.sub]
    out = Path(args.output) if args.output else None
    all_data: list = []

    for sub in subreddits:
        console.rule(f"[bold]r/{sub}[/bold]", style="bright_blue")
        _scrape_sub(sub, args, out, all_data)

    if out:
        label = "_".join(subreddits)
        scraper.save_json(all_data, out / f"full_{label}_{TIMESTAMP}.json")
        console.print("\n  [dim]All data saved to[/dim] " + str(out) + "/")


# ── news ──────────────────────────────────────────────────────────────────────

def cmd_news(args):
    from scraper.display import console, print_news_header
    subreddits = args.subreddits if args.subreddits else [args.sub]
    categories = args.categories if args.categories else None

    print_news_header(subreddits, args.sort)

    all_news = []
    for sub in subreddits:
        posts = scraper.get_posts(sub, sort=args.sort, limit=args.limit, method=args.method)
        filtered = scraper.filter_news_posts(posts, categories=categories)
        all_news.extend(filtered)
        console.print(f"[dim]r/{sub}: {len(filtered)}/{len(posts)} posts matched[/dim]")

    if not all_news:
        console.print("\n[dim]No news/leaks/results found with current filters.[/dim]")
        return

    console.print()
    for post in all_news:
        tag = scraper.tag_text(post.title)
        scraper.print_news_post(post, tag)

    if args.comments:
        for post in all_news[:args.comments_limit]:
            console.rule(f"COMMENTS: {post.title[:60]}")
            try:
                comments = scraper.get_comments(post.permalink, max_comments=50, method=args.method)
                notable = scraper.find_notable_comments(comments, min_score=3)
                if notable:
                    scraper.print_notable(notable)
                else:
                    scraper.print_comments(comments, max_depth=1)
            except Exception as exc:
                console.print(f"  [red]ERROR:[/red] {exc}")

    if args.output:
        out = Path(args.output)
        scraper.save_posts_csv(all_news, out / f"news_{'_'.join(subreddits)}_{TIMESTAMP}.csv")
        scraper.save_json(
            [p.__dict__ for p in all_news],
            out / f"news_{'_'.join(subreddits)}_{TIMESTAMP}.json",
        )


# ── analyze ───────────────────────────────────────────────────────────────────

def cmd_analyze(args):
    import json
    from scraper.analyzer import analyze_post, print_analysis

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Expected a list of {post, comments} objects.")
        return

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY or pass --api-key")
        return

    results = []
    for entry in data[:args.limit]:
        p = entry.get("post", {})
        from scraper.comments import Comment

        def _from_dict(d: dict) -> Comment:
            c = Comment(
                id=d.get("id", ""),
                author=d.get("author", ""),
                score=d.get("score", 0),
                depth=d.get("depth", 0),
                body=d.get("body", ""),
                created=d.get("created", ""),
                permalink=d.get("permalink", ""),
            )
            c.replies = [_from_dict(r) for r in d.get("replies", [])]
            return c

        comments = [_from_dict(c) for c in entry.get("comments", [])]
        analysis = analyze_post(
            p.get("title", ""),
            p.get("permalink", ""),
            comments,
            api_key=api_key,
            model=args.model,
        )
        print_analysis(analysis)
        results.append({
            "post_id": p.get("id"),
            "post_title": p.get("title"),
            "analysis": analysis.raw,
        })

    if args.output:
        out = Path(args.output)
        scraper.save_json(results, out / f"analysis_{path.stem}_{TIMESTAMP}.json")


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="reddit-scraper", description="Reddit fight/combat scraper")
    p.add_argument("--output", "-o", default="output")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable INFO-level logging")
    sub = p.add_subparsers(dest="cmd", required=True)

    # posts
    pp = sub.add_parser("posts", help="List posts from a subreddit")
    pp.add_argument("--sub", default="MMA")
    pp.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising"])
    pp.add_argument("--limit", type=int, default=25)
    pp.add_argument("--method", default="auto", choices=["auto", "api", "browser"], help=METHOD_HELP)

    # comments
    cp = sub.add_parser("comments", help="Scrape comments from a post URL")
    cp.add_argument("--url", required=True)
    cp.add_argument("--max-comments", type=int, default=500)
    cp.add_argument("--depth", type=int, default=3)
    cp.add_argument("--method", default="auto", choices=["auto", "api", "browser"], help=METHOD_HELP)
    cp.add_argument("--sentiment", action="store_true", help="Add sentiment scores to output")
    cp.add_argument("--min-score", type=int, default=5, help="Min upvotes for notable comment detection")

    # scrape
    sp = sub.add_parser("scrape", help="Scrape posts + comments (one or more subreddits)")
    sp.add_argument("--sub", default="MMA")
    sp.add_argument("--subreddits", nargs="+", metavar="SUB")
    sp.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising"])
    sp.add_argument("--limit", type=int, default=10, help="Posts per subreddit")
    sp.add_argument("--max-comments", type=int, default=200, help="Total comments per post")
    sp.add_argument("--depth", type=int, default=3)
    sp.add_argument("--method", default="auto", choices=["auto", "api", "browser"], help=METHOD_HELP)
    sp.add_argument("--sentiment", action="store_true", help="Add sentiment scores to output")
    sp.add_argument("--analyze", action="store_true", help="Run Claude AI analysis on each post")
    sp.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    sp.add_argument("--model", default="claude-haiku-4-5-20251001",
                    help="Claude model for analysis (default: haiku)")

    # news
    np = sub.add_parser("news", help="Show only breaking news, leaks, and fight results")
    np.add_argument("--sub", default="MMA")
    np.add_argument("--subreddits", nargs="+", metavar="SUB")
    np.add_argument("--sort", default="new", choices=["hot", "new", "top", "rising"])
    np.add_argument("--limit", type=int, default=50, help="Posts to scan (default: 50)")
    np.add_argument("--categories", nargs="+", choices=["news", "result", "leak", "hype"],
                    help="Filter to specific categories (default: all)")
    np.add_argument("--method", default="auto", choices=["auto", "api", "browser"], help=METHOD_HELP)
    np.add_argument("--comments", action="store_true", help="Also fetch notable comments for each post")
    np.add_argument("--comments-limit", type=int, default=5, help="Max posts to fetch comments for")

    # analyze
    ap = sub.add_parser("analyze", help="Run Claude AI analysis on a saved full_*.json file")
    ap.add_argument("--file", required=True, help="Path to a full_*.json output file")
    ap.add_argument("--limit", type=int, default=10, help="Max posts to analyze")
    ap.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")

    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    dispatch = {
        "posts": cmd_posts,
        "comments": cmd_comments,
        "scrape": cmd_scrape,
        "news": cmd_news,
        "analyze": cmd_analyze,
    }
    dispatch[args.cmd](args)
