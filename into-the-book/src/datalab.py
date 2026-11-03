"""네이버 데이터랩 통합검색어 트렌드 수집.

계획서 규칙
- 3-2: 책 1권 = 요청 1회 (여러 책을 묶으면 최댓값을 공유해서 작은 책이 눌림)
- 3-2: 응답에서 빠진 날은 0으로 채움 (데이터랩은 값 없는 기간을 아예 빼고 줌)
- 3-2: 주간 = 일간 합, 7일이 안 되는 주(양 끝)는 버림. 주는 월~일 (응답 period가 월요일)
- 3-3: 키워드 그룹 = "제목 저자", "저자 제목", "제목 책", "제목 소설"
- 하루 1,000회 한도: 호출 수를 파일에 기록하고, 받은 응답은 캐시해서 다시 부르지 않음
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, naver_keys

URL = "https://openapi.naver.com/v1/datalab/search"
DAILY_LIMIT = 1000
KST = timezone(timedelta(hours=9))
CACHE_DIR = RAW_DIR / "datalab"
CALL_LOG = RAW_DIR / "_datalab_calls.json"


# ── 3-3 키워드 규칙 ─────────────────────────────────────────
def title_rule(title: str) -> str:
    """'exclude' (2글자 이하) 또는 'ok'. 사전 단어 여부는 사람이 보고 dict_word로 넘긴다."""
    return "exclude" if len(title.replace(" ", "")) <= 2 else "ok"


def build_keywords(title: str, author: str, dict_word: bool = False) -> list[str]:
    """dict_word=True: 사전 단어 제목(예: 수족관)은 '제목 저자' 하나만 (3-3 수정안, 파일럿에서 비교)."""
    if dict_word:
        return [f"{title} {author}"]
    return [f"{title} {author}", f"{author} {title}", f"{title} 책", f"{title} 소설"]


# ── 호출 수 기록 ────────────────────────────────────────────
def _today() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def calls_today() -> int:
    if not CALL_LOG.exists():
        return 0
    return json.loads(CALL_LOG.read_text(encoding="utf-8")).get(_today(), 0)


def _count_call() -> None:
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(CALL_LOG.read_text(encoding="utf-8")) if CALL_LOG.exists() else {}
    log[_today()] = log.get(_today(), 0) + 1
    CALL_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


# ── 요청 ────────────────────────────────────────────────────
def _cache_path(book_id: str, start: str, end: str, unit: str, tag: str) -> Path:
    suffix = f"_{tag}" if tag else ""
    return CACHE_DIR / f"{book_id}_{start}_{end}_{unit}{suffix}.json"


def fetch(
    book_id: str,
    keywords: list[str],
    start: str,
    end: str,
    time_unit: str = "date",
    ages: list[str] | None = None,
    gender: str | None = None,
    tag: str = "",
    use_cache: bool = True,
    max_retries: int = 3,
) -> dict:
    """책 1권(키워드 그룹 1개)만 요청한다. 같은 조건이면 캐시를 돌려줘서 호출을 아낀다.

    tag: 같은 책을 다른 목적으로 받을 때 구분용 (예: 'cut' = 진입 직전 주까지 자른 요청).
    ages: 데이터랩 코드. '3' = 19~24세, '4' = 25~29세.
    """
    path = _cache_path(book_id, start, end, time_unit, tag)
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    if calls_today() >= DAILY_LIMIT:
        raise RuntimeError(f"오늘 호출 {DAILY_LIMIT}회 다 씀. 내일 이어서.")

    body = {
        "startDate": start,
        "endDate": end,
        "timeUnit": time_unit,
        "keywordGroups": [{"groupName": str(book_id), "keywords": keywords}],
    }
    if ages:
        body["ages"] = ages
    if gender:
        body["gender"] = gender

    cid, secret = naver_keys()
    headers = {
        "X-Naver-Client-Id": cid,
        "X-Naver-Client-Secret": secret,
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        res = requests.post(URL, json=body, headers=headers, timeout=30)
        _count_call()
        if res.status_code == 200:
            data = res.json()
            data["_request"] = body
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        if res.status_code in (429, 500, 502, 503) and attempt < max_retries:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:300]}")
    raise RuntimeError("unreachable")


# ── 응답 → 시계열 ────────────────────────────────────────────
def to_daily(resp: dict, start: str, end: str) -> pd.Series:
    """일간 응답을 요청 기간 전체 날짜로 펼치고, 빠진 날은 0."""
    if resp.get("timeUnit") != "date":
        raise ValueError("to_daily 는 time_unit='date' 응답에만 쓴다.")
    rows = resp["results"][0]["data"]
    s = pd.Series(
        {pd.Timestamp(r["period"]): float(r["ratio"]) for r in rows}, dtype="float64"
    )
    full = pd.date_range(start, end, freq="D")
    return s.reindex(full, fill_value=0.0).rename("ratio")


def daily_to_weekly(daily: pd.Series) -> pd.DataFrame:
    """월~일 주로 합산. index = 그 주 월요일. 7일이 안 되는 주는 버린다."""
    week_start = daily.index - pd.to_timedelta(daily.index.day_of_week, unit="D")
    g = daily.groupby(week_start)
    weekly = pd.DataFrame({"ratio": g.sum(), "n_days": g.size()})
    weekly = weekly[weekly["n_days"] == 7].drop(columns="n_days")
    weekly.index.name = "week"
    return weekly


def to_weekly_direct(resp: dict) -> pd.Series:
    """주간 직접 요청 응답 (일간 합과 비교용, 7장 3단계). 양 끝 주는 잘려 있을 수 있음."""
    rows = resp["results"][0]["data"]
    return pd.Series(
        {pd.Timestamp(r["period"]): float(r["ratio"]) for r in rows}, dtype="float64"
    ).rename("ratio")


def decimal_places(resp: dict) -> int:
    """응답 ratio 소수점 최대 자릿수 (7장 눌림 기준 '해상도 단계 수' 정할 때)."""
    best = 0
    for r in resp["results"][0]["data"]:
        text = repr(float(r["ratio"]))
        if "." in text:
            best = max(best, len(text.split(".")[1].rstrip("0")))
    return best
