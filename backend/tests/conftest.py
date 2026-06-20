"""테스트 공통 설정.

테스트는 개발/운영 DB와 분리된 임시 SQLite 파일을 사용한다. app 임포트(=엔진 생성)
이전에 `NTP_DATABASE_URL`을 설정해야 하므로, 이 모듈 최상단에서 환경변수를 지정한다.
"""
import os

os.environ["NTP_DATABASE_URL"] = "sqlite:///./test_ntp.sqlite3"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    """깨끗한 테스트 DB로 테이블 생성 → 종료 시 삭제. (TestClient는 lifespan 미실행)"""
    if os.path.exists("./test_ntp.sqlite3"):
        os.remove("./test_ntp.sqlite3")
    from app.db import init_db

    init_db()
    yield
    try:
        os.remove("./test_ntp.sqlite3")
    except OSError:
        pass
