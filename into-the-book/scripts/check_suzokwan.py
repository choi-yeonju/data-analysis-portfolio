"""수족관(유래혁) YES24 소설 일별 순위 추이 — 케이스 스터디가 YES24 데이터로 성립하는지 확인.

2024-01-08 ~ 2024-09-30 매주 월요일 (약 39일 × 최대 10페이지, 캐시돼서 다시 돌려도 호출 안 함)
실행:  python -m scripts.check_suzokwan
"""
import pandas as pd

from src import yes24

days = pd.date_range("2024-01-08", "2024-09-30", freq="W-MON")
print("날짜         순위 (1000위 밖이면 -)")
for d in days:
    r = yes24.find_book(d.strftime("%Y-%m-%d"), "수족관")
    bar = "" if r is None else "#" * max(1, (1001 - r) // 25)
    print(f"{d:%Y-%m-%d}  {r if r else '-':>5}  {bar}")
