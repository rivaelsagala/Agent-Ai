"""Shared data models for market-news collection and delivery."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CollectedNews:
    external_id: str
    canonical_url: str
    title: str
    published_at: Optional[datetime]
    source_excerpt: str = ""
    content_hash: str = ""
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NewsAnalysis:
    summary: str
    impact_reason: str
    category: str
    impact_level: int
    sentiment: float
    confidence: float
    tickers: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SendResult:
    provider_message_id: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
