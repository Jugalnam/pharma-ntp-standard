"""ORM 모델 (DS-010 영속 스키마).

Pydantic 도메인 모델([schemas])과 1:1 대응한다. 표준/장비/산출물/한계초과 로그를
SQLite/PostgreSQL에 영속한다.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StandardORM(Base):
    __tablename__ = "standards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    source_host: Mapped[str]
    max_offset_ms: Mapped[float]
    poll_interval_s: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)


class StandardHistoryORM(Base):
    """표준 변경 이력(URS-003/FS-002). 버전별 값 스냅샷 + 변경 사유를 append-only로 보존.

    인증(로그인) 부재로 행위자(actor)는 system/api로만 기록한다(한계 — Part 11 'who'
    완전 통제는 인증 도입 시).
    """

    __tablename__ = "standard_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int]
    version: Mapped[int]
    name: Mapped[str]
    source_host: Mapped[str]
    max_offset_ms: Mapped[float]
    poll_interval_s: Mapped[int]
    reason: Mapped[str] = mapped_column(default="")
    actor: Mapped[str] = mapped_column(default="system")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AssetORM(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    hostname: Mapped[str]
    gxp_critical: Mapped[bool] = mapped_column(default=False)
    standard_id: Mapped[int | None] = mapped_column(default=None)


class DeliverableORM(Base):
    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]
    title: Mapped[str]
    status: Mapped[str]
    requirement_tags: Mapped[list] = mapped_column(JSON, default=list)


class AlertORM(Base):
    """한계초과 로그(FS-023). 감사 추적 대체 핵심 이벤트 기록."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int]
    asset_name: Mapped[str] = mapped_column(default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    offset_ms: Mapped[float]
    limit_ms: Mapped[float | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="OPEN")
