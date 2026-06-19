"""도메인 스키마 (DS-010 데이터 모델).

초기 골격은 Pydantic 모델 + 인메모리 저장소를 사용한다.
후속 반복에서 SQLAlchemy ORM(PostgreSQL)으로 전환한다.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


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
    max_offset_ms: float = 1000.0
    poll_interval_s: int = 60


class TimeStandard(TimeStandardIn):
    id: int
    version: int = 1


# --- Asset (FS-010~012) ---
class AssetIn(BaseModel):
    name: str
    hostname: str
    gxp_critical: bool = False
    standard_id: int | None = None


class Asset(AssetIn):
    id: int


# --- OffsetSample (FS-020/021) ---
class OffsetSample(BaseModel):
    asset_id: int
    measured_at: datetime
    offset_ms: float
    stratum: int | None = None


# --- Alert (FS-022/023) ---
class Alert(BaseModel):
    id: int
    asset_id: int
    opened_at: datetime
    closed_at: datetime | None = None
    offset_ms: float
    status: AlertStatus = AlertStatus.OPEN


# --- Deliverable (FS-030~032) ---
class DeliverableIn(BaseModel):
    type: DeliverableType
    title: str
    requirement_tags: list[str] = Field(default_factory=list)


class Deliverable(DeliverableIn):
    id: int
    status: DeliverableStatus = DeliverableStatus.DRAFT
