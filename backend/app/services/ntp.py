"""NTP 오프셋 측정 (FS-020).

KRISS UTC(k) 등 신뢰 시간 소스에 질의하여 로컬 대비 오프셋(ms)을 측정한다.
[RISK-004] 단발 측정의 네트워크 지연 오탐을 줄이기 위해 다중 샘플 중앙값을 사용한다.

[FS-051] 측정은 NTP 클라이언트 모드(mode 3) **읽기**로만 수행한다. 시각 설정·
제어 모드(mode 6/7)를 사용하지 않으므로 대상 장비의 시각·설정을 변경하지 않는다.
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


def is_plausible_offset(offset_ms: float, bound_ms: float) -> bool:
    """오프셋 절댓값이 합리적 범위(bound) 이내면 True (FS-052, RISK-009).

    스푸핑/이상치로 비현실적으로 큰 오프셋이 들어오면 기준 시각을 신뢰하지 않는다.

    >>> is_plausible_offset(120.0, 3_600_000.0)
    True
    >>> is_plausible_offset(-5_000_000.0, 3_600_000.0)
    False
    """
    return abs(offset_ms) <= bound_ms
