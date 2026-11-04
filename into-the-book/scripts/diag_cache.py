"""이미 받은 YES24 캐시만 읽어서 확인 (API 호출 0회).

1. 짧은 페이지(100개 미만)가 몇 페이지에서 나오는지. 1페이지가 짧으면 Top100에 빈칸이 생겨 진입 판정에 영향
2. salePoint(판매지수)가 날짜마다 다른지. 다르면 '과거 시점 값'이라 결과 변수 후보가 됨
실행:  python -m scripts.diag_cache
"""
import json
from collections import Counter

from src import yes24

folder = yes24.CACHE_DIR / yes24.NOVEL
files = sorted(folder.glob("*_p??.json"))
print(f"캐시 파일 {len(files)}개 ({folder})")

short = Counter()
pages = Counter()
sale = {}
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    if d["status"] != 200:
        continue
    day, page = f.stem.split("_")[0], int(f.stem[-2:])
    n = len(d["items"])
    pages[page] += 1
    if 0 < n < 100:
        short[page] += 1
    for it in d["items"]:
        if str(it.get("itemId")) == "124235834":
            sale[day] = it.get("salePoint")

print("\n[1] 페이지 번호별: 받은 날 수 / 100개 미만인 날 수")
for p in sorted(pages):
    print(f"    {p:>2}페이지: {pages[p]:>3}일 / 짧음 {short[p]}일")

print("\n[2] 수족관(itemId 124235834) salePoint, 날짜별")
for day in sorted(sale):
    print(f"    {day}: {sale[day]}")
vals = set(sale.values())
print(f"    서로 다른 값 {len(vals)}개 → "
      + ("날짜마다 달라짐: 과거 시점 값일 가능성" if len(vals) > 1 else "전부 같음: 현재 값을 붙여주는 것"))
