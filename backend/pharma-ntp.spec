# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 스펙 — 포터블 단일 폴더(onedir) 배포본.

빌드(backend/ 에서):
    .venv\\Scripts\\python.exe -m PyInstaller pharma-ntp.spec --noconfirm --clean

산출: backend/dist/pharma-ntp-standard/  (실행: pharma-ntp-standard.exe)
번들: run.py(진입) + app 패키지 + frontend/dist(→ frontend_dist) + Python 런타임.
첫 실행 시 DB는 %ProgramData%\\PharmaNTP\\pharma_ntp.sqlite3 에 자동 생성(코드/데이터 분리).
"""
import os

from PyInstaller.utils.hooks import collect_submodules

here = os.path.abspath(SPECPATH)  # = backend/
frontend_dist = os.path.abspath(os.path.join(here, "..", "frontend", "dist"))

# app 내부의 동적 임포트(db.init_db의 app.models.orm 등)와 uvicorn 런타임 모듈을 모두 수집.
hiddenimports = collect_submodules("app") + collect_submodules("uvicorn")

a = Analysis(
    ["run.py"],
    pathex=[here],
    binaries=[],
    datas=[(frontend_dist, "frontend_dist")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pharma-ntp-standard",
    console=True,  # 콘솔 유지: 실행 상태·로그 표시, Ctrl+C로 종료
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="pharma-ntp-standard",
)
