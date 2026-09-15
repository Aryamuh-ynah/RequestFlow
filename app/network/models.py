from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(slots=True)
class RequestConfig:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: str = ""
    timeout_seconds: int = 30


@dataclass(slots=True)
class RequestResult:
    status_code: int
    status_text: str

    effective_url: str

    content_type: str
    http_version: str

    total_time_ms: float
    response_size: int

    response_headers: str
    body: bytes