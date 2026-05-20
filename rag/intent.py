"""Heuristic intent detection for user prompts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PromptIntent(str, Enum):
    """Whether a prompt should be answered from the API or via Gemma."""

    DEFINITIVE = "definitive"
    CONVERSATIONAL = "conversational"


@dataclass(frozen=True)
class IntentResult:
    intent: PromptIntent
    reason: str


_QUESTION_STARTERS = re.compile(
    r"^\s*("
    r"what|who|whom|which|when|where|why|how|"
    r"is|are|was|were|do|does|did|can|could|will|would|should|has|have|had"
    r")\b",
    re.IGNORECASE,
)

_DEFINITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(how many|how much|how often)\b", re.I), "quantity question"),
    (re.compile(r"\b(what was|what is|what were|what are)\b", re.I), "fact lookup"),
    (re.compile(r"\b(who (led|won|scored|averaged|had|is|was|threw))\b", re.I), "who question"),
    (re.compile(r"\b(how did|how does|how do)\b", re.I), "performance question"),
    (re.compile(r"\b(average[ds]?|stats?|statline|fantasy points?|fppg|ppg)\b", re.I), "stats terms"),
    (re.compile(r"\b(yards?|touchdowns?|tds?|receptions?|targets?|carries|attempts?)\b", re.I), "football counting stats"),
    (re.compile(r"\b(ppr|half[- ]?ppr|standard scoring|snap share|target share|red[- ]?zone)\b", re.I), "fantasy terms"),
    (re.compile(r"\b(week \d{1,2}|matchup|projection|start[- ]?sit)\b", re.I), "weekly fantasy context"),
    (re.compile(r"\b(injury|injured|questionable|doubtful|out|ir|trade[d]?|waiver)\b", re.I), "injury/roster terms"),
    (re.compile(r"\b\d{4}\s*(season|stats?)?\b"), "season reference"),
    (re.compile(r"\b\d+(\.\d+)?\s*%"), "percentage"),
    (re.compile(r"\b\d+(\.\d+)?\s*(yds|yards|tds|rec|tgt|car)\b", re.I), "rate stat"),
)

_CONVERSATIONAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*(hi|hello|hey|thanks|thank you)\b", re.I), "greeting"),
    (re.compile(r"\b(what do you think|in your opinion|do you believe)\b", re.I), "opinion"),
    (re.compile(r"\b(should i draft|would you draft|dynasty value)\b", re.I), "draft advice"),
    (re.compile(r"\b(explain like|eli5|tell me a story|write a|poem|joke)\b", re.I), "creative"),
    (re.compile(r"\b(brainstorm|ideas? for|help me (think|decide))\b", re.I), "open-ended help"),
    (re.compile(r"\b(compare .+ (vs\.?|versus|or) .+ (opinion|better overall))\b", re.I), "subjective compare"),
    (re.compile(r"\b(best (ever|of all time)|goat|all[- ]time greatest)\b", re.I), "subjective ranking"),
    (re.compile(r"\b(why do you think|why is fantasy football)\b", re.I), "general discussion"),
)


def detect_prompt_intent(prompt: str) -> IntentResult:
    """Classify whether a prompt needs a definitive DB-backed answer or open chat.

    Definitive prompts are routed to the read-only API (search/retrieval).
    Conversational prompts are sent directly to Gemma without API retrieval.
    """
    text = prompt.strip()
    if not text:
        return IntentResult(
            PromptIntent.CONVERSATIONAL,
            reason="empty prompt",
        )

    definitive_score = 0
    conversational_score = 0
    definitive_reasons: list[str] = []
    conversational_reasons: list[str] = []

    for pattern, label in _CONVERSATIONAL_PATTERNS:
        if pattern.search(text):
            conversational_score += 4
            conversational_reasons.append(label)

    for pattern, label in _DEFINITIVE_PATTERNS:
        if pattern.search(text):
            definitive_score += 2
            definitive_reasons.append(label)

    if conversational_score == 0:
        if text.endswith("?"):
            definitive_score += 2
            definitive_reasons.append("question mark")

        if _QUESTION_STARTERS.search(text):
            definitive_score += 2
            definitive_reasons.append("question starter")

    word_count = len(text.split())
    if word_count <= 12 and re.search(
        r"\b(stats?|statline|overview|splits|profile|report|summary|projection)\b",
        text,
        re.I,
    ):
        definitive_score += 2
        definitive_reasons.append("stats lookup phrase")

    if definitive_score > conversational_score:
        reason = ", ".join(definitive_reasons) or "factual question signals"
        return IntentResult(PromptIntent.DEFINITIVE, reason=reason)

    if conversational_score > 0:
        reason = ", ".join(conversational_reasons)
        return IntentResult(PromptIntent.CONVERSATIONAL, reason=reason)

    if text.endswith("?") or _QUESTION_STARTERS.search(text):
        return IntentResult(
            PromptIntent.DEFINITIVE,
            reason="unclassified question defaulting to API",
        )

    return IntentResult(
        PromptIntent.CONVERSATIONAL,
        reason="no definitive signals; defaulting to Gemma",
    )
