"""NTP 오프셋 측정 (FS-020).

KRISS UTC(k) 등 신뢰 시간 소스에 질의하여 로컬 대비 오프셋(ms)을 측정한다.
[RISK-004] 단발 측정의 네트워크 지연 오탐을 줄이기 위해 다중 샘플 중앙값을 사용한다.
"""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median

import ntplib

from app.config import settings


@dataclass
class NtpResult:
    offset_ms: float
    stratum: int


def measure_offset(host: str, samples: int = 3, timeout: float | None = None) -> NtpResult:
    """host(NTP 서버)에 질의해 오프셋(ms)과 stratum을 반환한다.

    samples회 측정 후 오프셋 중앙값을 취해 일시적 네트워크 지연을 완화한다(RISK-004).
    """
    timeout = timeout if timeout is not None else settings.ntp_timeout_s
    client = ntplib.NTPClient()
    offsets: list[float] = []
    last_stratum = 16
    for _ in range(max(1, samples)):
        resp = client.request(host, version=3, timeout=timeout)
        offsets.append(resp.offset * 1000.0)  # 초 → ms
        last_stratum = resp.stratum
    return NtpResult(offset_ms=median(offsets), stratum=last_stratum)
