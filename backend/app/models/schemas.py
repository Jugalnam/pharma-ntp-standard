"""도메인 스키마 (DS-010 데이터 모델).

Pydantic 도메인 모델. 영속 대상(표준/장비/산출물/한계초과 로그)은 SQLAlchemy
ORM([models/orm])과 1:1 대응하며 `from_attributes`로 변환한다. 실시간 측정값은
모니터링 엔진의 인메모리 상태로 유지한다(폴링으로 재생성).
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class DeliverableType(str, Enum):
    IQ = "IQ"
    OQ = "OQ"
    PQ = "PQ"


class DeliverableStatus(str, Enum):
    DRAFT = "Draft"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    EFFECTIVE = "Effective"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# --- TimeStandard (FS-001/002) ---
class TimeStandardIn(BaseModel):
    name: str
    source_host: str = "time.kriss.re.kr"
    max_offset_ms: float = Field(default=1000.0, ge=0)
    poll_interval_s: int = Field(default=60, ge=1)  # 0/음수 폴링 주기 방지


class TimeStandardUpdate(TimeStandardIn):
    """표준 수정(PUT) 입력. 변경 사유를 함께 받아 이력에 기록한다(URS-003/FS-002)."""
    reason: str | None = None


class TimeStandard(TimeStandardIn):
    model_config = ConfigDict(from_attributes=True)  # ORM → Pydantic 변환
    id: int
    version: int = 1


class StandardHistory(BaseModel):
    """표준 변경 이력 항목(URS-003). 버전별 값 스냅샷 + 사유."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    standard_id: int
    version: int
    name: str
    source_host: str
    max_offset_ms: float
    poll_interval_s: int
    reason: str = ""
    actor: str = "system"
    changed_at: datetime


# --- Asset (FS-010~012) ---
class AssetIn(BaseModel):
    name: str
    hostname: str
    gxp_critical: bool = False
    standard_id: int | None = None


class Asset(AssetIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- OffsetSample (FS-020/021) ---
class OffsetSample(BaseModel):
    asset_id: int
    measured_at: datetime
    offset_ms: float
    stratum: int | None = None


# --- Alert / 한계초과 로그 (FS-022/023) ---
class Alert(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_id: int
    asset_name: str = ""          # 로그 가독성(장비 삭제 후에도 보존)
    opened_at: datetime
    closed_at: datetime | None = None
    offset_ms: float
    limit_ms: float | None = None  # 초과 당시 허용 한계
    status: AlertStatus = AlertStatus.OPEN


# --- Deliverable (FS-030~032) ---
class DeliverableIn(BaseModel):
    type: DeliverableType
    title: str
    requirement_tags: list[str] = Field(default_factory=list)


class Deliverable(DeliverableIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: DeliverableStatus = DeliverableStatus.DRAFT
