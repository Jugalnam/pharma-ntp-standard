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
class PollResult:
    """폴링 1회 결과. 장비 응답 여부와 기준 보정 여부를 함께 전달한다."""
    asset_id: int
    reachable: bool
    sample: OffsetSample | None = None       # 응답 시 보정된 오프셋 샘플
    reference_synced: bool = True            # KRISS 기준 보정 성공 여부(FS-052)
    detail: str | None = None                # 무응답/오류 사유


@dataclass
class Monitor:
    """인메모리 모니터링 상태 저장소(현 증분).

    후속 증분에서 SQLAlchemy 영속 저장소로 대체한다.
    """
    latest: dict[int, OffsetSample] = field(default_factory=dict)   # asset_id -> 최신 샘플
    alerts: list[Alert] = field(default_factory=list)               # 전체 경고 이력(FS-023)
    unreachable: dict[int, datetime] = field(default_factory=dict)  # asset_id -> 최근 무응답 시각(FS-020)
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
        self.unreachable.pop(asset.id, None)  # 응답 성공 → 무응답 표시 해제

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

    # --- 무응답 기록 (FS-020, RISK-003) ---
    def record_unreachable(
        self, asset: Asset, at: datetime | None = None, detail: str | None = None,
    ) -> PollResult:
        """장비가 NTP 질의에 응답하지 않음을 기록한다(UNREACHABLE)."""
        at = at or _now()
        self.unreachable[asset.id] = at
        return PollResult(asset_id=asset.id, reachable=False, detail=detail)

    # --- 실측 폴링 (FS-020) ---
    def poll(
        self,
        asset: Asset,
        standard: TimeStandard,
        measure: MeasureFn | None = None,
        at: datetime | None = None,
    ) -> PollResult:
        """장비 자신(asset.hostname)에 NTP 질의해 시각 오차를 수집·기록한다(FS-020).

        로컬 시계 미신뢰(URS-041) 원칙상 오프셋은 KRISS 기준으로 보정한다:
          장비 vs KRISS = (장비 vs PC) − (KRISS vs PC)
        이로써 모니터링 PC 자체 시계 오차가 상쇄된다. 장비 무응답은 UNREACHABLE로,
        기준(KRISS) 도달 실패는 미보정(reference_synced=False)으로 구분한다.

        measure 주입으로 테스트에서 네트워크 의존을 분리한다(기본: 실측).
        """
        measure = measure or (lambda host: measure_offset(host))
        at = at or _now()

        # 1) 장비 시각 측정 (PC 대비). 무응답 → UNREACHABLE.
        try:
            dev = measure(asset.hostname)
        except Exception as e:  # 도달 실패/타임아웃
            return self.record_unreachable(asset, at=at, detail=str(e))

        # 2) 기준(KRISS) 대비 PC 오프셋으로 보정.
        reference_synced = True
        try:
            ref = measure(standard.source_host)
            offset_vs_ref = dev.offset_ms - ref.offset_ms
        except Exception:  # 기준 도달 실패 — 미보정 PC 대비값으로 폴백
            offset_vs_ref = dev.offset_ms
            reference_synced = False

        sample = self.record_sample(
            asset, standard, offset_ms=offset_vs_ref, stratum=dev.stratum, at=at,
        )
        return PollResult(
            asset_id=asset.id, reachable=True, sample=sample,
            reference_synced=reference_synced,
        )

    # --- 상태 판정 (FS-021, RISK-003) ---
    def status_of(
        self, asset: Asset, standard: TimeStandard, now: datetime | None = None,
    ) -> str:
        """대시보드 상태: UNKNOWN / UNREACHABLE / STALE / BREACH / OK (우선순위 순)."""
        now = now or _now()
        sample = self.latest.get(asset.id)
        # 무응답이 최신 샘플보다 나중(또는 샘플 없음)이면 UNREACHABLE (FS-020, RISK-003)
        unreach_at = self.unreachable.get(asset.id)
        if unreach_at is not None and (sample is None or unreach_at >= sample.measured_at):
            return "UNREACHABLE"
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
