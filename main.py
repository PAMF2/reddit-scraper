"""
reddit-scraper CLI

Usage examples:
  python main.py posts --sub MMA --sort hot --limit 20
  python main.py comments --url https://www.reddit.com/r/MMA/comments/...
  python main.py scrape --sub MMA --sort hot --limit 10 --max-comments 50
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

import scraper

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
    comments = scraper.get_comments(args.url, max_comments=args.max_comments)
    scraper.print_comments(comments, max_depth=args.depth)
    if args.output:
        out = Path(args.output)
        slug = args.url.rstrip("/").split("/")[-1][:40]
        flat = []
        def walk(c, parent=""):
            flat.append({**c.__dict__, "replies": None, "parent_id": parent})
            for r in c.replies:
                walk(r, c.id)
        for c in comments:
            walk(c)
        scraper.save_json([scraper.export._comment_to_dict(c) for c in comments],
                          out / f"comments_{slug}_{TIMESTAMP}.json")
        scraper.save_comments_csv(comments, out / f"comments_{slug}_{TIMESTAMP}.csv")


def cmd_scrape(args):
    """Scrape posts + their comments from a subreddit in one shot."""
    posts = scraper.get_posts(args.sub, sort=args.sort, limit=args.limit)
    scraper.print_posts(posts)

    out = Path(args.output) if args.output else None
    if out:
        scraper.save_posts_csv(posts, out / f"posts_{args.sub}_{TIMESTAMP}.csv")

    all_data = []
    for i, post in enumerate(posts, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(posts)}] {post.title}")
        print(f"{'='*70}")
        try:
            comments = scraper.get_comments(post.permalink, max_comments=args.max_comments)
        except Exception as exc:
            print(f"  ERROR fetching comments: {exc}")
            continue

        scraper.print_comments(comments, max_depth=args.depth)

        post_data = {
            "post": post.__dict__,
            "comments": [scraper.export._comment_to_dict(c) for c in comments],
        }
        all_data.append(post_data)

        if out:
            slug = post.id or post.title[:20].replace(" ", "_")
            scraper.save_comments_csv(comments, out / f"comments_{slug}_{TIMESTAMP}.csv", post.id)

    if out:
        scraper.save_json(all_data, out / f"full_{args.sub}_{TIMESTAMP}.json")
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
    cp.add_argument("--max-comments", type=int, default=100)
    cp.add_argument("--depth", type=int, default=3, help="Max display depth")

    # scrape (all-in-one)
    sp = sub.add_parser("scrape", help="Scrape posts + comments from a subreddit")
    sp.add_argument("--sub", default="MMA", help="Subreddit (default: MMA)")
    sp.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising"])
    sp.add_argument("--limit", type=int, default=10, help="How many posts to scrape")
    sp.add_argument("--max-comments", type=int, default=50, help="Comments per post")
    sp.add_argument("--depth", type=int, default=3, help="Max display depth")

    return p


if __name__ == "__main__":
    # make export accessible for cmd_comments
    import scraper.export as _export
    scraper.export = _export

    parser = build_parser()
    args = parser.parse_args()

    dispatch = {"posts": cmd_posts, "comments": cmd_comments, "scrape": cmd_scrape}
    dispatch[args.cmd](args)
