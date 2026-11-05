"""⛔ 사용 중단 (2026-11-05): YES24가 1:1 문의에 "수집·저장 불가"로 답함 (PILOT_LOG 11-05).
이 모듈은 파일럿 기록과 테스트용으로만 남긴다. YES24_ALLOW_FETCH 를 켜지 말 것.

YES24 일별 베스트셀러 수집 (결과 변수 소스. 알라딘 OpenAPI는 2026-11-01 종료).

확인된 사실 (2026-11-03, scripts/check_yes24*.py)
- 소설: categoryId 001001046 (국내도서>소설/시/희곡)
- 과거 데이터 시작일 2023-05-20 (그 전은 404 BEST_001)
- 하루 최대 1000위, pageSize 최대 100
- sortOrder는 '페이지 안 순서' → 실제 순위 = (page-1)*pageSize + sortOrder
- 한도: 하루 20,000회(계정 단위), 초당 10회

약관 메모: 대량·체계적 축적으로 별도 DB를 만드는 행위 금지 조항이 있음.
원본은 data/raw 에만 두고(커밋 안 함) 공개는 집계 결과만. 수집 전 1:1 문의로 학습용 허용 여부 확인.
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import requests

from .config import RAW_DIR, get_key

URL = "https://apis.yes24.com/v1/category/bestsellerDaily"
NOVEL = "001001046"
DATA_START = "2023-05-20"
PAGE_SIZE = 100
DEPTH = 200  # 수집·분석 깊이. YES24 문의 범위(1~200위)에 맞춤 (2026-11-04). 이미 받은 1000위 캐시도 분석엔 200위까지만
# 범위 밖 순위는 max_rank + 1 (기본 201). 0을 쓰면 rank <= 100 비교에서 진입으로 잡혀서 위험했음 (2026-11-04)
ALLOW_ENV = "YES24_ALLOW_FETCH"  # 이 환경변수가 "1"일 때만 API 호출. 약관 문의 답 오기 전에는 캐시만 읽는다
MIN_INTERVAL = 0.15  # 초당 10회 제한보다 여유 있게
CACHE_DIR = RAW_DIR / "yes24"

_last_call = 0.0


class YES24Error(RuntimeError):
    pass


def _get(params: dict, max_retries: int = 4) -> requests.Response:
    global _last_call
    if os.getenv(ALLOW_ENV) != "1":
        raise YES24Error(f"API 호출 막힘: 약관 문의 답 오기 전에는 캐시만 읽음 ({ALLOW_ENV}=1 일 때만 호출)")
    headers = {"X-Api-Key": get_key("YES24_API_KEY")}
    for attempt in range(1, max_retries + 1):
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        r = requests.get(URL, headers=headers, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return r
    raise YES24Error(f"재시도 {max_retries}회 실패: HTTP {r.status_code} {r.text[:200]}")


def fetch_page(day: str, page: int, category: str = NOVEL, use_cache: bool = True,
               age: int | None = None, sex: str | None = None) -> list[dict] | None:
    """한 페이지(100권). 데이터가 없는 날(404 BEST_001)은 None. 그 밖의 오류는 예외."""
    tag = f"_a{age}" if age else ""
    tag += f"_s{sex}" if sex else ""
    path = CACHE_DIR / category / f"{day}{tag}_p{page:02d}.json"
    if use_cache and path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached["items"] if cached["status"] == 200 else None

    params = {"categoryId": category, "date": day, "page": page,
              "pageSize": PAGE_SIZE, "detail": "Y"}
    if age:
        params["age"] = age
    if sex:
        params["sex"] = sex
    r = _get(params)

    if r.status_code == 404:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if body.get("errorCode") != "BEST_001":
            raise YES24Error(f"404 {r.text[:200]}")
        items, status = None, 404
    elif r.status_code == 200:
        items, status = (r.json().get("data") or {}).get("items") or [], 200
    else:
        raise YES24Error(f"HTTP {r.status_code}: {r.text[:200]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status, "items": items or []}, ensure_ascii=False),
                    encoding="utf-8")
    return items


def fetch_day(day: str, max_rank: int = DEPTH, category: str = NOVEL, **kw) -> pd.DataFrame:
    """그날 1~max_rank위. 열: date, rank, itemId, isbn13, title, author, publisher, publishDate, salePoint."""
    rows, short_pages, no_data, empty_first = [], [], False, False
    for page in range(1, (max_rank - 1) // PAGE_SIZE + 2):
        items = fetch_page(day, page, category, **kw)
        if items is None and page == 1:
            no_data = True
        if items == [] and page == 1:
            empty_first = True   # 200 응답인데 목록이 빔 = 데이터 이상
        if not items:
            break
        if len(items) < PAGE_SIZE:
            short_pages.append(page)
        for it in items:
            rank = (page - 1) * PAGE_SIZE + int(it["sortOrder"])
            if rank > max_rank:
                break
            rows.append({
                "date": pd.Timestamp(day), "rank": rank, "itemId": it.get("itemId"),
                "isbn13": it.get("isbn13"), "title": it.get("title"),
                "author": it.get("author"), "publisher": it.get("publisher"),
                "publishDate": it.get("publishDate"), "salePoint": it.get("salePoint"),
            })
        # 주의: 중간 페이지도 99개만 올 때가 있음 (2026-11-03 확인). 짧은 페이지에서 멈추지 않는다.
    df = pd.DataFrame(rows)
    df.attrs["short_pages"] = short_pages  # 100개 미만으로 온 페이지 번호 (1페이지면 Top100에 빈칸)
    df.attrs["no_data"] = no_data          # 그날 데이터 자체가 없음 (404)
    df.attrs["empty_first"] = empty_first  # 1페이지가 200 응답인데 빈 목록
    if not df.empty:
        df = df.drop_duplicates("itemId").sort_values("rank").reset_index(drop=True)
    return df


def find_rank(day: str, *, isbn13: str | None = None, item_id: str | None = None,
              max_rank: int = DEPTH, **kw) -> int | None:
    """그날 순위. max_rank 밖이면 max_rank + 1 (기본 201).
    그날 데이터가 없거나(404) 1페이지가 빈 목록이면 None.
    None은 숫자 비교에서 바로 에러가 나서 '데이터 없음'이 조용히 섞이지 않는다.
    제목이 아니라 ISBN13 또는 itemId로 찾는다 (동명 책 혼입 방지)."""
    if not (isbn13 or item_id):
        raise ValueError("isbn13 또는 item_id 중 하나는 필요")
    df = fetch_day(day, max_rank, **kw)
    if df.attrs.get("no_data") or df.attrs.get("empty_first") or df.empty:
        return None
    col, val = ("isbn13", isbn13) if isbn13 else ("itemId", item_id)
    hit = df[df[col].astype(str) == str(val)]
    return int(hit["rank"].min()) if not hit.empty else max_rank + 1
