"""YES24 일별 베스트셀러 수집 (결과 변수 소스. 알라딘 OpenAPI는 2026-11-01 종료).

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
import time

import pandas as pd
import requests

from .config import RAW_DIR, get_key

URL = "https://apis.yes24.com/v1/category/bestsellerDaily"
NOVEL = "001001046"
DATA_START = "2023-05-20"
PAGE_SIZE = 100
MIN_INTERVAL = 0.15  # 초당 10회 제한보다 여유 있게
CACHE_DIR = RAW_DIR / "yes24"

_last_call = 0.0


class YES24Error(RuntimeError):
    pass


def _get(params: dict, max_retries: int = 4) -> requests.Response:
    global _last_call
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


def fetch_day(day: str, max_rank: int = 1000, category: str = NOVEL, **kw) -> pd.DataFrame:
    """그날 1~max_rank위. 열: date, rank, itemId, isbn13, title, author, publisher, publishDate, salePoint."""
    rows = []
    for page in range(1, (max_rank - 1) // PAGE_SIZE + 2):
        items = fetch_page(day, page, category, **kw)
        if not items:
            break
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
    if not df.empty:
        df = df.drop_duplicates("itemId").sort_values("rank").reset_index(drop=True)
    return df


def find_book(day: str, title_prefix: str, max_rank: int = 1000, **kw) -> int | None:
    """그날 title_prefix 로 시작하는 책의 순위 (없으면 None)."""
    df = fetch_day(day, max_rank, **kw)
    if df.empty:
        return None
    hit = df[df["title"].str.startswith(title_prefix, na=False)]
    return int(hit["rank"].min()) if not hit.empty else None
