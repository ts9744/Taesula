import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVER_URL = os.getenv("SERVER_URL")
MAIN_GUI_SIZE = os.getenv("MAIN_GUI_SIZE")

if not SERVER_URL:
    raise ValueError("SERVER_URL이 .env 파일에 설정되어 있지 않습니다.")