"""YES24 일별 베스트셀러가 결과 소스로 쓸 수 있는지 점검 (호출 약 8회).

확인할 것
1. 소설 카테고리 ID
2. 과거 날짜를 몇 년 전까지 주는지 (계획: 2022-12부터, 가능하면 2020-12부터)
3. 몇 위까지 나오는지 (계획: Top200)

실행:  python -m scripts.check_yes24
       python -m scripts.check_yes24 <categoryId>   ← 1단계에서 찾은 소설 ID로 다시 실행
"""
import sys

import os
if os.getenv("YES24_ALLOW_FETCH") != "1":
    raise SystemExit("재실행 금지: YES24 약관 문의 답 오기 전 (11-03 점검용, 결과는 PILOT_LOG)")

import requests

from src.config import get_key

BASE = "https://apis.yes24.com/v1/category"
HEADERS = {"X-Api-Key": get_key("YES24_API_KEY")}


def get(path, **params):
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, params=params, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    return r.status_code, body


if len(sys.argv) < 2:
    status, body = get("list")
    print("카테고리 목록 HTTP", status)
    data = body.get("data", {})
    rows = data.get("data", data) if isinstance(data, dict) else data
    for c in rows if isinstance(rows, list) else []:
        name = str(c.get("categoryName", ""))
        if "소설" in name or "문학" in name or str(c.get("categoryId", "")) == "001":
            print(c)
    print("\n소설 categoryId를 골라서:  python -m scripts.check_yes24 <categoryId>")
    sys.exit()

cat = sys.argv[1]
dates = ["2026-10-01", "2025-01-02", "2024-01-02", "2023-01-02", "2022-12-01", "2020-12-01", "2018-01-02"]

print(f"categoryId={cat}")
print(f"{'date':<12} {'HTTP':>4} {'items':>5} {'totalCount':>10}  1위 / 마지막 순위")
for d in dates:
    status, body = get("bestsellerDaily", categoryId=cat, date=d, page=1, pageSize=100)
    data = body.get("data") or {}
    items = data.get("items") or []
    first = items[0]["title"] if items else body.get("errorCode") or body.get("message")
    last = items[-1].get("sortOrder") if items else "-"
    print(f"{d:<12} {status:>4} {len(items):>5} {str(data.get('totalCount', '-')):>10}  {first} / {last}")

# 200위까지 나오는지
status, body = get("bestsellerDaily", categoryId=cat, date="2024-01-02", page=2, pageSize=100)
items = (body.get("data") or {}).get("items") or []
print(f"\n2024-01-02 2페이지(101~200위): HTTP {status}, {len(items)}개",
      f"마지막 순위 {items[-1].get('sortOrder')}" if items else "")
