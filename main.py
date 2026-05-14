"""
reddit-scraper CLI

Usage examples:
  python main.py posts --sub MMA --sort hot --limit 20
  python main.py comments --url https://www.reddit.com/r/MMA/comments/...
  python main.py scrape --sub MMA --sort hot --limit 10 --max-comments 200
  python main.py scrape --subreddits MMA ufc boxing --sort hot --limit 5 --max-comments 100
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

import scraper
import scraper.export as _export
scraper.export = _export

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def cmd_posts(args):
    posts = scraper.get_posts(args.sub, sort=args.sort, limit=args.limit)
    scraper.print_posts(posts)
    if args.output:
        out = Path(args.output)
        scraper.save_posts_csv(posts, out / f"posts_{args.sub}_{TIMESTAMP}.csv")
        scraper.save_json([p.__dict__ for p in posts], out / f"posts_{args.sub}_{TIMESTAMP}.json")


def cmd_comments(args):
    comments = scraper.get_comments(args.url, max_comments=args.max_comments, method=args.method)
    scraper.print_comments(comments, max_depth=args.depth)
    if args.output:
        out = Path(args.output)
        slug = args.url.rstrip("/").split("/")[-1][:40]
        scraper.save_json([scraper.export._comment_to_dict(c) for c in comments],
                          out / f"comments_{slug}_{TIMESTAMP}.json")
        scraper.save_comments_csv(comments, out / f"comments_{slug}_{TIMESTAMP}.csv")


def _scrape_subreddit(sub: str, args, out: Path | None, all_data: list) -> None:
    """Scrape one subreddit and append results to all_data."""
    posts = scraper.get_posts(sub, sort=args.sort, limit=args.limit)
    scraper.print_posts(posts)

    if out:
        scraper.save_posts_csv(posts, out / f"posts_{sub}_{TIMESTAMP}.csv")

    for i, post in enumerate(posts, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(posts)}] r/{sub} — {post.title}")
        print(f"{'='*70}")
        try:
            comments = scraper.get_comments(
                post.permalink,
                max_comments=args.max_comments,
                method=args.method,
            )
        except Exception as exc:
            print(f"  ERROR fetching comments: {exc}")
            continue

        scraper.print_comments(comments, max_depth=args.depth)

        all_data.append({
            "post": post.__dict__,
            "comments": [scraper.export._comment_to_dict(c) for c in comments],
        })

        if out:
            slug = post.id or post.title[:20].replace(" ", "_")
            scraper.save_comments_csv(comments, out / f"comments_{slug}_{TIMESTAMP}.csv", post.id)


def cmd_scrape(args):
    """Scrape posts + their comments from one or more subreddits."""
    subreddits = args.subreddits if args.subreddits else [args.sub]

    out = Path(args.output) if args.output else None
    all_data: list = []

    for sub in subreddits:
        print(f"\n{'#'*70}")
        print(f"  Subreddit: r/{sub}")
        print(f"{'#'*70}")
        _scrape_subreddit(sub, args, out, all_data)

    if out:
        label = "_".join(subreddits)
        scraper.save_json(all_data, out / f"full_{label}_{TIMESTAMP}.json")
        print(f"\n[done] All data saved to {out}/")


def build_parser():
    p = argparse.ArgumentParser(prog="reddit-scraper", description="Reddit fight/combat scraper")
    p.add_argument("--output", "-o", default="output", help="Output directory (default: output/)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # posts
    pp = sub.add_parser("posts", help="List posts from a subreddit")
    pp.add_argument("--sub", default="MMA", help="Subreddit name (default: MMA)")
    pp.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising"])
    pp.add_argument("--limit", type=int, default=25)

    # comments
    cp = sub.add_parser("comments", help="Scrape comments from a post URL")
    cp.add_argument("--url", required=True, help="Full post URL")
    cp.add_argument("--max-comments", type=int, default=500)
    cp.add_argument("--depth", type=int, default=3, help="Max display depth")
    cp.add_argument("--method", default="auto", choices=["auto", "api", "browser"],
                    help="Fetch method: auto (default), api, or browser")

    # scrape (all-in-one)
    sp = sub.add_parser("scrape", help="Scrape posts + comments from one or more subreddits")
    sp.add_argument("--sub", default="MMA", help="Subreddit (default: MMA) — use --subreddits for multiple")
    sp.add_argument("--subreddits", nargs="+", metavar="SUB",
                    help="One or more subreddits (overrides --sub)")
    sp.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising"])
    sp.add_argument("--limit", type=int, default=10, help="How many posts to scrape per subreddit")
    sp.add_argument("--max-comments", type=int, default=200, help="Max comments per post")
    sp.add_argument("--depth", type=int, default=3, help="Max display depth")
    sp.add_argument("--method", default="auto", choices=["auto", "api", "browser"],
                    help="Fetch method: auto (default), api, or browser")

    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {"posts": cmd_posts, "comments": cmd_comments, "scrape": cmd_scrape}
    dispatch[args.cmd](args)
