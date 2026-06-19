"""FastAPI 진입점 (DS-001).

pharma-ntp-standard 백엔드. KRISS UTC(k)를 기준 표준으로 하는
시각 동기화 모니터링·검증 API를 제공한다.
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
