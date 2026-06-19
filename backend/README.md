# Backend (FastAPI)

KRISS UTC(k) 기준 시각 동기화 모니터링·검증 API.

## 설치 / 실행

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash / PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/api/health

## 테스트

```bash
pytest
```

핵심 테스트:
- `tests/test_alerts.py` — 오프셋 경고 경계값 (RISK-001 / OQ-022)
- `tests/test_api.py` — health, 표준 버전 증가, 상태 전이 규칙 (RISK-005)

## 구조

| 경로 | 역할 |
|------|------|
| `app/main.py` | FastAPI 진입점, CORS, 라우터 등록 |
| `app/config.py` | 환경 설정 (기준 NTP 소스 등) |
| `app/api/routes.py` | REST 라우터 (DS-020) |
| `app/services/alerts.py` | 오프셋 경고 판정 (RISK-001 핵심) |
| `app/services/ntp.py` | NTP 오프셋 측정 (FS-020) |
| `app/models/schemas.py` | 도메인 스키마 (DS-010) |

## 현재 상태(골격)

저장소는 **인메모리**다. 후속 반복에서 SQLAlchemy(SQLite→PostgreSQL)와
오프셋 폴링 워커, 감사 추적(FS-040)을 연결한다. 설계 근거는 [`../docs/`](../docs/README.md) 참조.
