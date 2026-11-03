"""API 키는 코드에 쓰지 않고 into-the-book/.env 에서만 읽는다."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

load_dotenv(PROJECT_DIR / ".env")


def get_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} 가 비어 있음. into-the-book/.env 에 {name}=값 을 넣어줘 "
            f"(.env.example 참고)."
        )
    return value


def naver_keys() -> tuple[str, str]:
    return get_key("NAVER_CLIENT_ID"), get_key("NAVER_CLIENT_SECRET")
