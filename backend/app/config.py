"""애플리케이션 설정.

DS-001 §6 구성 항목(IQ 대상)을 환경변수로 노출한다.

배포(포터블/설치형) 시 **코드와 데이터를 분리**한다(DS-040 후속). DB는 실행 폴더가
아니라 영속 데이터 폴더에 둔다 — 재설치·업그레이드 때 감시·경고 기록(데이터 무결성
대상)이 보존되도록. 우선순위: `NTP_DATABASE_URL`(명시) > `NTP_DATA_DIR` 기반 기본값.
"""
import os
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_data_dir() -> Path:
    """영속 데이터(SQLite·로그)를 둘 폴더를 결정한다.

    1) `NTP_DATA_DIR` 환경변수가 있으면 그곳.
    2) 배포(PyInstaller 프리즈) 실행이면 OS 표준 데이터 폴더(`%ProgramData%\\PharmaNTP`).
    3) 개발 실행이면 `backend/`(기존 동작 유지 — 개발 DB 위치 불변).
    """
    env = os.environ.get("NTP_DATA_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):  # PyInstaller 등으로 번들된 실행본
        base = os.environ.get("PROGRAMDATA") or str(Path.home())
        return Path(base) / "PharmaNTP"
    return Path(__file__).resolve().parent.parent  # = backend/


def _default_database_url() -> str:
    data_dir = resolve_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'pharma_ntp.sqlite3').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NTP_")

    # 기준 표준: KRISS UTC(k) (URS-001)
    default_ntp_host: str = "time.kriss.re.kr"
    # 기본 허용 오프셋 한계(ms) — 표준에서 재정의 가능
    default_max_offset_ms: float = 1000.0
    # 폴링 주기(초)
    default_poll_interval_s: int = 60
    # NTP 질의 타임아웃(초)
    ntp_timeout_s: float = 5.0
    # 기준 시각 합리적 범위(ms) — 초과 시 스푸핑/이상치로 보고 미신뢰(FS-052, RISK-009). 기본 1시간.
    ntp_sanity_bound_ms: float = 3_600_000.0
    # 주기적 백그라운드 폴링 스케줄러(FS-024). tick마다 깨어나 due 장비를 측정.
    scheduler_enabled: bool = True
    scheduler_tick_s: float = 10.0
    # 한 사이클에서 동시에 폴링할 장비 수(무응답 장비가 순차 대기로 전체를 막지 않게).
    scheduler_concurrency: int = 10
    # 영속 데이터 폴더(코드와 분리). 기본은 resolve_data_dir() 참조.
    data_dir: Path = Field(default_factory=resolve_data_dir)
    # DB 연결 문자열. 기본은 데이터 폴더의 SQLite. PostgreSQL 전환 시 이 값만 변경.
    database_url: str = Field(default_factory=_default_database_url)


settings = Settings()
