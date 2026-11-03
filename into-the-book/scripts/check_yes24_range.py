"""YES24 일별 베스트셀러 점검 2 (호출 최대 약 100회, 하루 한도 20,000회).

1. 과거 데이터 시작일: 2023-01-02(없음) ~ 2024-01-02(있음) 사이를 이분 탐색
2. sortOrder가 전체 순위인지 페이지 안 순서인지: 1·2페이지 책이 겹치는지, 순번이 어떻게 이어지는지
3. 1000위(10페이지)까지 실제로 나오는지

실행:  python -m scripts.check_yes24_range
"""
from datetime import date, timedelta

import requests

from src.config import get_key

URL = "https://apis.yes24.com/v1/category/bestsellerDaily"
HEADERS = {"X-Api-Key": get_key("YES24_API_KEY")}
CAT = "001001046"  # 국내도서>소설/시/희곡


def fetch(d: str, page: int = 1, size: int = 100):
    r = requests.get(URL, headers=HEADERS, timeout=30,
                     params={"categoryId": CAT, "date": d, "page": page, "pageSize": size})
    if r.status_code != 200:
        return None
    return (r.json().get("data") or {}).get("items") or []


# 1. 시작일 이분 탐색
lo, hi = date(2023, 1, 2), date(2024, 1, 2)   # lo: 없음, hi: 있음
while (hi - lo).days > 1:
    mid = lo + timedelta(days=(hi - lo).days // 2)
    if fetch(mid.isoformat(), size=1):
        hi = mid
    else:
        lo = mid
print(f"[1] 데이터 시작일: {hi}  (그 전날 {lo} 은 없음)")

# 시작일 이후가 연속인지 몇 군데 찍어보기
for d in [hi + timedelta(days=k) for k in (1, 7, 30, 90)]:
    print(f"    {d}: {'있음' if fetch(d.isoformat(), size=1) else '없음'}")

# 2. sortOrder 의미
d = "2024-06-03"
p1, p2 = fetch(d, 1), fetch(d, 2)
ids1 = {x["itemId"] for x in p1}
ids2 = {x["itemId"] for x in p2}
print(f"\n[2] {d} 1페이지 sortOrder {p1[0]['sortOrder']}~{p1[-1]['sortOrder']}, "
      f"2페이지 sortOrder {p2[0]['sortOrder']}~{p2[-1]['sortOrder']}")
print(f"    1·2페이지 겹치는 책: {len(ids1 & ids2)}권 (0이면 서로 다른 책)")
print(f"    2페이지 첫 책: {p2[0]['title']}")

# 3. 1000위까지
p10 = fetch(d, 10)
print(f"\n[3] {d} 10페이지(901~1000위): {len(p10) if p10 is not None else 'HTTP 오류'}개")

# 케이스 스터디 확인: 수족관이 2024년에 언제 보이는지 (월 1회 샘플, 1~1000위)
print("\n[덤] 수족관(유래혁) 순위, 매월 첫 월요일:")
for m in range(1, 9):
    first = date(2024, m, 1)
    monday = first + timedelta(days=(7 - first.weekday()) % 7)
    found = "-"
    for page in range(1, 11):
        items = fetch(monday.isoformat(), page)
        if not items:
            break
        hit = [x for x in items if x["title"].startswith("수족관")]
        if hit:
            found = (page - 1) * 100 + hit[0]["sortOrder"]
            break
    print(f"    {monday}: {found}")
