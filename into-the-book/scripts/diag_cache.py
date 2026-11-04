"""이미 받은 YES24 캐시만 읽어서 확인 (API 호출 0회).

주의: 순위 분포나 진입 여부는 출력하지 않는다 (사전 등록 전에 결과를 보지 않기 위해).

1. 짧은 페이지(100개 미만)가 몇 페이지에서 나오는지
2. 짧은 페이지의 sortOrder가 '빈 번호로 남는지'(순위 정확) '1~99로 다시 매겨지는지'(그 뒤 순위가 1씩 밀림)
3. salePoint가 날짜마다 다른지 — 캐시에 있는 '모든 책' 기준
실행:  python -m scripts.diag_cache
"""
import json
from collections import Counter, defaultdict

from src import yes24

folder = yes24.CACHE_DIR / yes24.NOVEL
files = sorted(folder.glob("*_p??.json"))
print(f"캐시 파일 {len(files)}개")

short, pages = Counter(), Counter()
short_detail = []
sale = defaultdict(set)
days_seen = defaultdict(set)
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    if d["status"] != 200:
        continue
    day, page = f.stem.split("_")[0], int(f.stem[-2:])
    items = d["items"]
    pages[page] += 1
    if 0 < len(items) < 100:
        short[page] += 1
        orders = sorted(int(x["sortOrder"]) for x in items)
        missing = sorted(set(range(1, orders[-1] + 1)) - set(orders))
        short_detail.append((day, page, len(items), orders[-1], missing))
    for it in items:
        sale[str(it.get("itemId"))].add(it.get("salePoint"))
        days_seen[str(it.get("itemId"))].add(day)

print("\n[1] 페이지 번호별: 받은 날 수 / 100개 미만인 날 수")
for p in sorted(pages):
    print(f"    {p:>2}페이지: {pages[p]:>3}일 / 짧음 {short[p]}일")

print("\n[2] 짧은 페이지의 sortOrder (10페이지 제외: 목록 끝이라 원래 짧을 수 있음)")
for day, page, n, mx, missing in short_detail:
    if page == 10:
        continue
    kind = "빈 번호 남음 → 순위 정확" if mx == 100 and missing else (
           "1~99로 다시 매김 → 그 뒤 순위 1씩 밀림" if mx == n else "기타")
    print(f"    {day} {page}페이지: {n}개, 최대 sortOrder {mx}, 빠진 번호 {missing} → {kind}")

# 하루만 나온 책은 값이 변할 수 없으니 비교 대상에서 뺀다 (2026-11-04 리뷰 지적)
repeat = [k for k, ds in days_seen.items() if len(ds) >= 2]
changed = [k for k in repeat if len(sale[k]) > 1]
print(f"\n[3] salePoint: 캐시의 책 {len(days_seen)}권 중 2일 이상 나온 책 {len(repeat)}권, 그중 값이 달라진 책 {len(changed)}권")
print("    0권이면 → 과거 날짜를 조회해도 같은 값(현재 값). 결과 변수로 못 씀")
