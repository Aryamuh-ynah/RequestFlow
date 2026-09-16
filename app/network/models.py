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


@dataclass(slots=True, frozen=True)
class NetworkStage:
    key: str
    label: str
    start_ms: float
    end_ms: float
    duration_ms: float
    skipped: bool = False


@dataclass(slots=True, frozen=True)
class NetworkTimings:
    dns_ms: float
    tcp_ms: float
    tls_ms: float
    pre_transfer_ms: float
    first_byte_wait_ms: float
    download_ms: float
    total_ms: float

    name_lookup_at_ms: float
    connect_at_ms: float
    app_connect_at_ms: float
    pre_transfer_at_ms: float
    start_transfer_at_ms: float

    primary_ip: str = ""
    primary_port: int = 0

    stages: tuple[NetworkStage, ...] = ()


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

    timings: NetworkTimings