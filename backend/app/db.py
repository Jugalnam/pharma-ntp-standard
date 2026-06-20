"""영속 저장소 (DS-010 / DS-040 후속 증분).

SQLAlchemy 엔진·세션·Base를 제공한다. 개발은 SQLite 파일, 운영은 PostgreSQL로
`NTP_DATABASE_URL`(config.database_url)만 바꿔 전환한다.

저장 대상: 표준/장비/산출물/한계초과 로그(영속). 실시간 측정값(오프셋·도달성)은
폴링으로 재생성되므로 모니터링 엔진의 인메모리 상태로 유지한다.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


# SQLite는 다중 스레드(스케줄러 to_thread) 접근을 위해 check_same_thread=False 필요.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, future=True
)


def init_db() -> None:
    """테이블을 생성한다(존재하면 무시). 앱 기동 시 1회 호출."""
    from app.models import orm  # noqa: F401  (모델 등록)

    Base.metadata.create_all(engine)
