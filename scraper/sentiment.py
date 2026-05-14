"""
Sentiment analysis for Reddit comments.
Uses VADER with fight-community lexicon additions.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False

# Fight-community words that VADER misscores
_FIGHT_LEXICON: dict[str, float] = {
    # Excitement (VADER treats profanity as negative even in hype context)
    "insane": 1.5,
    "wtf": 0.8,
    "holy": 0.5,
    "goat": 2.5,
    "beast": 2.0,
    "savage": 1.8,
    "vicious": 1.2,
    "nasty": 1.0,        # "nasty knockout" = good in fight context
    "sick": 1.0,         # "sick finish" = good
    "filthy": 1.0,       # "filthy combo" = good
    "disgusting": 0.8,   # "disgusting power" = good
    "brutal": 1.0,       # "brutal KO" = hype
    "clean": 1.5,        # "clean shot"
    "slept": 0.5,        # "got slept" (KO) - neutral in context
    "robbed": -2.0,      # "got robbed" = strong negative opinion
    "trash": -1.5,
    "awful": -2.0,
    "boring": -2.0,
    "embarassing": -2.0,
    "pathetic": -2.0,
    "disgrace": -2.0,
    "juicer": -1.5,
    "cheater": -2.0,
}


@dataclass
class SentimentResult:
    compound: float      # -1.0 to +1.0
    positive: float      # 0.0 to 1.0
    negative: float
    neutral: float
    label: str           # "positive" | "negative" | "neutral"
    intensity: str       # "strong" | "moderate" | "weak"


def _make_analyzer() -> "SentimentIntensityAnalyzer | None":
    if not _VADER_AVAILABLE:
        return None
    a = SentimentIntensityAnalyzer()
    a.lexicon.update(_FIGHT_LEXICON)
    return a


_analyzer = _make_analyzer()


def _label(compound: float) -> tuple[str, str]:
    if compound >= 0.5:
        return "positive", "strong"
    if compound >= 0.05:
        return "positive", "moderate" if compound >= 0.25 else "weak"
    if compound <= -0.5:
        return "negative", "strong"
    if compound <= -0.05:
        return "negative", "moderate" if compound <= -0.25 else "weak"
    return "neutral", "weak"


def analyze(text: str) -> SentimentResult:
    """Return sentiment scores for a piece of text."""
    if not _analyzer or not text.strip():
        return SentimentResult(0.0, 0.0, 0.0, 1.0, "neutral", "weak")

    scores = _analyzer.polarity_scores(text)
    label, intensity = _label(scores["compound"])
    return SentimentResult(
        compound=round(scores["compound"], 3),
        positive=round(scores["pos"], 3),
        negative=round(scores["neg"], 3),
        neutral=round(scores["neu"], 3),
        label=label,
        intensity=intensity,
    )


def analyze_thread(comments: list) -> dict:
    """
    Aggregate sentiment across a comment tree.
    Returns distribution + overall compound average.
    """
    from .comments import Comment

    all_scores: list[float] = []
    counts: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}

    def _walk(nodes: list[Comment]) -> None:
        for c in nodes:
            if c.body:
                r = analyze(c.body)
                all_scores.append(r.compound)
                counts[r.label] += 1
            _walk(c.replies)

    _walk(comments)

    if not all_scores:
        return {"avg_compound": 0.0, "label": "neutral", "distribution": counts, "total": 0}

    avg = round(sum(all_scores) / len(all_scores), 3)
    label, _ = _label(avg)
    return {
        "avg_compound": avg,
        "label": label,
        "distribution": counts,
        "total": len(all_scores),
    }
