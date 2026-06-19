"""모니터링 엔진 (FS-020/021/022/023).

장비별 NTP 오프셋 샘플을 수집·보관하고, 표준 허용 한계 대비 경고를
생성/해제한다. 본 모듈이 측정([ntp.py])과 경고 판정([alerts.py])을
실제 운영 흐름으로 연결한다.

위험 대응:
- [RISK-001] is_offset_breach를 실측 샘플에 연결해 한계 초과를 경고(FS-022).
- [RISK-003] last_sync 노후(stale)를 감지해 폴링 중단을 드러낸다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from app.models.schemas import (
    Asset, TimeStandard, OffsetSample, Alert, AlertStatus,
)
from app.services.alerts import is_offset_breach
from app.services.ntp import measure_offset, NtpResult

# 노후 판정 계수: poll_interval_s * STALE_FACTOR 를 넘겨 미수집이면 STALE.
STALE_FACTOR = 3

MeasureFn = Callable[[str], NtpResult]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Monitor:
    """인메모리 모니터링 상태 저장소(현 증분).

    후속 증분에서 SQLAlchemy 영속 저장소로 대체한다.
    """
    latest: dict[int, OffsetSample] = field(default_factory=dict)   # asset_id -> 최신 샘플
    alerts: list[Alert] = field(default_factory=list)               # 전체 경고 이력(FS-023)
    _open: dict[int, Alert] = field(default_factory=dict)           # asset_id -> 미해제 경고
    _alert_seq: int = 0

    # --- 샘플 기록 + 경고 판정 (FS-022/023, RISK-001) ---
    def record_sample(
        self,
        asset: Asset,
        standard: TimeStandard,
        offset_ms: float,
        stratum: int | None = None,
        at: datetime | None = None,
    ) -> OffsetSample:
        """오프셋 샘플 1건을 기록하고 경고 상태를 갱신한다.

        - 한계 초과(절댓값) & 미해제 경고 없음 → 경고 OPEN 생성.
        - 한계 이내 & 미해제 경고 있음        → 경고 CLOSED 전이.
        경계 규칙은 [is_offset_breach]를 그대로 따른다(한계와 같으면 합격).
        """
        at = at or _now()
        sample = OffsetSample(
            asset_id=asset.id, measured_at=at, offset_ms=offset_ms, stratum=stratum,
        )
        self.latest[asset.id] = sample

        breach = is_offset_breach(offset_ms, standard.max_offset_ms)
        if breach and asset.id not in self._open:
            self._alert_seq += 1
            alert = Alert(
                id=self._alert_seq, asset_id=asset.id, opened_at=at,
                offset_ms=offset_ms, status=AlertStatus.OPEN,
            )
            self._open[asset.id] = alert
            self.alerts.append(alert)
        elif not breach and asset.id in self._open:
            alert = self._open.pop(asset.id)
            alert.status = AlertStatus.CLOSED
            alert.closed_at = at
        return sample

    # --- 실측 폴링 (FS-020) ---
    def poll(
        self,
        asset: Asset,
        standard: TimeStandard,
        measure: MeasureFn | None = None,
    ) -> OffsetSample:
        """표준의 source_host에 NTP 질의해 샘플을 수집·기록한다.

        measure 주입으로 테스트에서 네트워크 의존을 분리한다(기본: 실측).
        """
        measure = measure or (lambda host: measure_offset(host))
        res = measure(standard.source_host)
        return self.record_sample(
            asset, standard, offset_ms=res.offset_ms, stratum=res.stratum,
        )

    # --- 상태 판정 (FS-021, RISK-003) ---
    def status_of(
        self, asset: Asset, standard: TimeStandard, now: datetime | None = None,
    ) -> str:
        """대시보드 상태: UNKNOWN / STALE / BREACH / OK (우선순위 순)."""
        now = now or _now()
        sample = self.latest.get(asset.id)
        if sample is None:
            return "UNKNOWN"
        age_s = (now - sample.measured_at).total_seconds()
        if age_s > standard.poll_interval_s * STALE_FACTOR:
            return "STALE"
        if is_offset_breach(sample.offset_ms, standard.max_offset_ms):
            return "BREACH"
        return "OK"

    def dashboard_row(
        self, asset: Asset, standard: TimeStandard | None, default_max_ms: float,
        now: datetime | None = None,
    ) -> dict:
        sample = self.latest.get(asset.id)
        limit = standard.max_offset_ms if standard else default_max_ms
        return {
            "asset_id": asset.id,
            "name": asset.name,
            "gxp_critical": asset.gxp_critical,
            "offset_ms": sample.offset_ms if sample else None,
            "max_offset_ms": limit,
            "stratum": sample.stratum if sample else None,
            "status": self.status_of(asset, standard, now) if standard else (
                "UNKNOWN" if sample is None else "OK"
            ),
            "last_sync": sample.measured_at.isoformat() if sample else None,
        }
