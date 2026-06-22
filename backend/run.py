"""포터블 실행 진입점.

단일 프로세스로 API+UI(빌드된 프런트)를 localhost 한 포트에 띄우고 브라우저를 연다.
PyInstaller 번들의 진입 스크립트로 사용한다.

환경변수: NTP_HOST(기본 127.0.0.1) · NTP_PORT(기본 8000) · NTP_NO_BROWSER(설정 시 자동 오픈 안 함).
데이터(SQLite)는 app.config.resolve_data_dir()이 정한 영속 폴더에 생성된다.
"""
import os
import sys
import threading
import webbrowser


def _setup_console_encoding() -> None:
    """Windows 콘솔(기본 cp949)에서 유니코드 출력 크래시/깨짐을 방지한다.

    cp949 콘솔에 em-dash·한글 등을 print하면 UnicodeEncodeError로 죽을 수 있어,
    출력 코드페이지를 UTF-8로 바꾸고 표준스트림 인코딩을 utf-8로 재설정한다.
    """
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


_setup_console_encoding()

import uvicorn  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

HOST = os.environ.get("NTP_HOST", "127.0.0.1")
PORT = int(os.environ.get("NTP_PORT", "8000"))
URL = f"http://{HOST}:{PORT}"


def _open_browser() -> None:
    if not os.environ.get("NTP_NO_BROWSER"):
        webbrowser.open(URL)


def main() -> None:
    print(f"pharma-ntp-standard - {URL}")
    print(f"  data dir: {settings.data_dir}")
    print(f"  DB: {settings.database_url}")
    print("  stop: Ctrl+C in this window")
    # 서버가 뜬 뒤 브라우저 오픈(앱 객체를 직접 넘겨 프리즈 환경에서도 안전).
    threading.Timer(1.5, _open_browser).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
