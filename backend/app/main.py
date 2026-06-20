"""FastAPI 진입점 (DS-001).

pharma-ntp-standard 백엔드. KRISS UTC(k)를 기준 표준으로 하는
시각 동기화 모니터링·검증 API를 제공한다.

[FS-050] 기본 배포는 루프백 바인딩(uvicorn 기본 host 127.0.0.1)을 전제로 한다.
내부망에 노출할 경우 인증 게이트를 두어야 한다(외부 인터넷 노출 금지).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="pharma-ntp-standard API",
    description="제약(GxP) 환경 NTP 시간 표준 — KRISS UTC(k) 준거 모니터링·검증",
    version="0.1.0",
)

# 개발 프런트(Vite 기본 포트) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": "pharma-ntp-standard", "docs": "/docs"}
