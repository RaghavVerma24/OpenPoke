"""Lightweight deterministic retrieval for existing execution agents."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "can", "do", "for", "from",
    "get", "help", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "please", "the", "to", "we", "with", "you", "your", "did", "has", "have",
    "find", "look", "search", "check", "near", "call", "what", "where", "when",
    "remains", "need", "get", "recommend", "explain", "translate",
}
_SYNONYMS = {
    "reply": "email", "replied": "email", "respond": "email", "response": "email",
    "inbox": "email", "mail": "email", "message": "email", "messages": "email",
    "flight": "travel", "flights": "travel", "airline": "travel", "fly": "travel",
    "hotel": "lodging", "hotels": "lodging", "stay": "lodging", "accommodation": "lodging",
    "restaurant": "dining", "restaurants": "dining", "food": "dining", "eat": "dining",
    "reservation": "booking", "reserve": "booking", "book": "booking",
    "meeting": "calendar", "schedule": "calendar", "appointment": "calendar",
    "remind": "reminder", "reminders": "reminder", "task": "todo", "tasks": "todo",
    "follow": "reminder", "followup": "reminder", "followups": "reminder",
    "groceries": "grocery", "shopping": "grocery", "store": "grocery",
    "buy": "grocery", "buying": "grocery",
    "live": "launch", "goes": "launch",
}


def _tokens(text: str) -> list[str]:
    result = []
    for raw in _TOKEN_RE.findall(text.lower()):
        token = _SYNONYMS.get(raw, raw)
        if token not in _STOP_WORDS and len(token) > 1:
            result.append(token)
    return result


@dataclass(frozen=True)
class AgentProfile:
    """Small searchable view; deliberately excludes full agent history."""

    name: str
    description: str = ""
    task_type: str = ""
    entities: tuple[str, ...] = ()
    last_active: str = ""

    @property
    def searchable_text(self) -> str:
        return " ".join((self.name, self.description, self.task_type, *self.entities))


@dataclass(frozen=True)
class RouteResult:
    candidates: tuple[AgentProfile, ...]
    scores: tuple[float, ...]
    best_score: float
    matched: bool


class AgentRouter:
    """Rank existing agents by lexical relevance and exact entity overlap."""

    def __init__(self, top_k: int = 4, threshold: float = 0.29):
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        self.top_k = top_k
        self.threshold = threshold

    def route(self, query: str, agents: Iterable[AgentProfile]) -> RouteResult:
        query_tokens = _tokens(query)
        query_set = set(query_tokens)
        raw_tokens = _TOKEN_RE.findall(query)
        query_entities = {
            raw.lower() for raw in _TOKEN_RE.findall(query)
            if raw[:1].isupper() and raw.lower() not in _STOP_WORDS
            and raw != (raw_tokens[0] if raw_tokens else "")
        }
        ranked: list[tuple[float, AgentProfile]] = []
        unique_agents = {agent.name.casefold(): agent for agent in agents}
        for agent in unique_agents.values():
            profile_tokens = _tokens(agent.searchable_text)
            profile_set = set(profile_tokens)
            overlap = query_set & profile_set
            if not query_set or not profile_set or not overlap:
                score = 0.0
            else:
                # Weighted Jaccard rewards precise overlap while dampening generic words.
                idf = {
                    token: 1.0 + math.log(1 + 1 / max(1, profile_tokens.count(token)))
                    for token in overlap
                }
                intersection = sum(idf.values())
                union = len(query_set | profile_set)
                score = intersection / (intersection + union - len(overlap))
                named_overlap = query_entities & profile_set
                if named_overlap:
                    score = min(1.0, score + 0.25 * len(named_overlap))
                # A match on a distinctive agent title is stronger than description-only overlap.
                name_tokens = set(_tokens(agent.name))
                if query_set & name_tokens:
                    score = min(1.0, score + 0.12)
            ranked.append((score, agent))

        # Stable tie break by name makes results reproducible across roster ordering.
        ranked.sort(key=lambda item: (-item[0], item[1].name.casefold()))
        selected = [(score, agent) for score, agent in ranked[: self.top_k] if score > 0]
        best_score = selected[0][0] if selected else 0.0
        matched = best_score >= self.threshold
        if not matched:
            selected = []
        return RouteResult(
            candidates=tuple(agent for _, agent in selected),
            scores=tuple(score for score, _ in selected),
            best_score=best_score,
            matched=matched,
        )


def profiles_from_roster(names: Iterable[str], log_store) -> list[AgentProfile]:
    """Build compact profiles from names and the latest request (not full history)."""
    profiles = []
    for name in names:
        recent = log_store.load_recent(name, limit=8)
        requests = [payload for tag, _, payload in recent if tag == "agent_request"]
        description = requests[-1][:240] if requests else ""
        last_active = recent[-1][1] if recent else ""
        profiles.append(AgentProfile(name=name, description=description, last_active=last_active))
    return profiles
