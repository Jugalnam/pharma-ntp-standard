"""애플리케이션 설정.

DS-001 §6 구성 항목(IQ 대상)을 환경변수로 노출한다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # 운영 DB로 전환 시 사용 (현재 골격은 인메모리 저장소)
    database_url: str = "sqlite:///./pharma_ntp.sqlite3"


settings = Settings()
