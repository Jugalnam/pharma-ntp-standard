"""FastAPI 진입점 (DS-001).

pharma-ntp-standard 백엔드. KRISS UTC(k)를 기준 표준으로 하는
시각 동기화 모니터링·검증 API를 제공한다.

[FS-050] 기본 배포는 루프백 바인딩(uvicorn 기본 host 127.0.0.1)을 전제로 한다.
내부망에 노출할 경우 인증 게이트를 두어야 한다(외부 인터넷 노출 금지).

배포(포터블/설치형) 시에는 빌드된 프런트(`frontend/dist`)를 **이 앱이 직접 서빙**해
단일 포트로 API+UI를 함께 제공한다(개발은 Vite가 별도 서빙하므로 dist가 없으면 생략).
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router, run_scheduler, hydrate_from_db
from app.config import settings
from app.db import init_db


def _frontend_dir() -> Path | None:
    """서빙할 프런트 빌드 폴더를 찾는다(없으면 None → 개발: Vite 사용)."""
    env = os.environ.get("NTP_FRONTEND_DIR")
    if env:
        p = Path(env)
        return p if (p / "index.html").exists() else None
    if getattr(sys, "frozen", False):  # PyInstaller 번들
        p = Path(getattr(sys, "_MEIPASS", ".")) / "frontend_dist"
        return p if (p / "index.html").exists() else None
    p = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    return p if (p / "index.html").exists() else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명주기: DB 초기화·경고 로그 복원 후 폴링 스케줄러(FS-024)를 기동·정리한다."""
    init_db()  # 테이블 생성(존재 시 무시)
    hydrate_from_db()  # 영속 한계초과 로그로 모니터 상태 복원(재시작 후)
    task = asyncio.create_task(run_scheduler()) if settings.scheduler_enabled else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="pharma-ntp-standard API",
    description="제약(GxP) 환경 NTP 시간 표준 — KRISS UTC(k) 준거 모니터링·검증",
    version="0.1.0",
    lifespan=lifespan,
)

# 개발 프런트(Vite 기본 포트) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 프런트 빌드가 있으면 SPA를 루트에 마운트(단일 포트). /api·/docs는 위에서 먼저 등록돼 우선.
_FRONTEND = _frontend_dir()
if _FRONTEND is not None:
    app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
else:

    @app.get("/")
    def root():
        # 개발 모드(빌드 없음): 프런트는 Vite(5173)에서, 여기선 API만 제공.
        return {"name": "pharma-ntp-standard", "docs": "/docs", "frontend": "dev: use Vite (5173)"}
