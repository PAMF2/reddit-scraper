"""
Claude-powered post analyzer.
Summarizes discussions, extracts fighter mentions, sentiments, and notable insights.
Requires ANTHROPIC_API_KEY env var or --api-key CLI flag.
"""
from __future__ import annotations
import os
import json
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class PostAnalysis:
    post_title: str
    summary: str
    overall_sentiment: str
    sentiment_reasoning: str
    fighter_mentions: list[str]
    key_topics: list[str]
    notable_quotes: list[str]
    is_breaking_news: bool
    news_summary: str
    raw: dict = field(default_factory=dict)


def _flatten_comments(comments: list, max_comments: int = 80) -> str:
    """Serialize comment tree to readable text for the prompt."""
    from .comments import Comment
    lines: list[str] = []

    def _walk(nodes: list[Comment], indent: int = 0) -> None:
        for c in nodes:
            if len(lines) >= max_comments:
                return
            prefix = "  " * indent
            score_tag = f"[+{c.score}]" if c.score >= 0 else f"[{c.score}]"
            lines.append(f"{prefix}{score_tag} u/{c.author}: {c.body}")
            _walk(c.replies, indent + 1)

    _walk(comments)
    return "\n".join(lines)


def analyze_post(
    post_title: str,
    post_url: str,
    comments: list,
    api_key: str | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> PostAnalysis:
    """
    Send a post + its top comments to Claude and return structured analysis.
    Uses claude-haiku by default (fast + cheap for batch analysis).
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Pass --api-key or set the environment variable."
        )

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=key)

    comment_text = _flatten_comments(comments, max_comments=80)
    if not comment_text:
        comment_text = "(no comments available)"

    prompt = f"""You are analyzing a Reddit post from a combat sports subreddit (MMA, boxing, BJJ, etc.).

POST TITLE: {post_title}
POST URL: {post_url}

TOP COMMENTS:
{comment_text}

Analyze this post and return a JSON object with exactly these fields:
{{
  "summary": "2-3 sentence summary of what the post is about and what the community is discussing",
  "overall_sentiment": "positive | negative | neutral | mixed",
  "sentiment_reasoning": "1 sentence explaining why the community feels this way",
  "fighter_mentions": ["list of fighter names mentioned (first and last name if possible)"],
  "key_topics": ["list of 3-6 main topics discussed e.g. 'judging controversy', 'PED use', 'fight technique'"],
  "notable_quotes": ["2-3 most insightful or representative comments verbatim"],
  "is_breaking_news": true or false,
  "news_summary": "if breaking news/leak/announcement: 1 sentence describing it. Otherwise empty string."
}}

Return ONLY the JSON object, no other text."""

    log.info("Claude: analyzing '%s...' with %s", post_title[:40], model)

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()

    # strip markdown code fences if Claude wraps the JSON
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text)

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        log.warning("Claude returned invalid JSON: %s\nRaw: %s", e, raw_text[:200])
        data = {}

    return PostAnalysis(
        post_title=post_title,
        summary=data.get("summary", ""),
        overall_sentiment=data.get("overall_sentiment", "unknown"),
        sentiment_reasoning=data.get("sentiment_reasoning", ""),
        fighter_mentions=data.get("fighter_mentions", []),
        key_topics=data.get("key_topics", []),
        notable_quotes=data.get("notable_quotes", []),
        is_breaking_news=bool(data.get("is_breaking_news", False)),
        news_summary=data.get("news_summary", ""),
        raw=data,
    )


def print_analysis(a: PostAnalysis) -> None:
    def _p(text: str) -> None:
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode())

    _p(f"\n{'='*70}")
    _p(f"  CLAUDE ANALYSIS: {a.post_title[:60]}")
    _p(f"{'='*70}")
    _p(f"\nSUMMARY")
    _p(f"  {a.summary}")
    _p(f"\nSENTIMENT: {a.overall_sentiment.upper()}")
    _p(f"  {a.sentiment_reasoning}")
    if a.is_breaking_news:
        _p(f"\n[BREAKING NEWS] {a.news_summary}")
    if a.fighter_mentions:
        _p(f"\nFIGHTERS MENTIONED: {', '.join(a.fighter_mentions)}")
    if a.key_topics:
        _p(f"\nKEY TOPICS:")
        for t in a.key_topics:
            _p(f"  - {t}")
    if a.notable_quotes:
        _p(f"\nNOTABLE QUOTES:")
        for q in a.notable_quotes:
            _p(f'  "{q[:120]}"')
    _p("")


# needed for the re.sub calls in analyze_post
import re  # noqa: E402
