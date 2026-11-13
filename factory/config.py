import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SERVER_URL = os.getenv("SERVER_URL")
MAIN_GUI_SIZE = os.getenv("MAIN_GUI_SIZE")
# 격자 지도 저장, 목적지 등록은 서버가 관리자 키를 요구한다 (서버 TAESULA_ADMIN_KEY 와 같은 값)
ADMIN_HEADERS = {"X-Admin-Key": os.getenv("TAESULA_ADMIN_KEY", "")}

if not SERVER_URL:
    raise ValueError("SERVER_URL이 .env 파일에 설정되어 있지 않습니다.")