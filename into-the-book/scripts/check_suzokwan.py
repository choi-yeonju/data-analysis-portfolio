"""[보관용, 재실행 불가] YES24 수집 불허(11-05)로 캐시 삭제. 결과는 PILOT_LOG 11-04 기록.

수족관(유래혁) YES24 소설 일별 순위 추이 — 매주 월요일 표본.

itemId 124235834로 찾는다 (diag_suzokwan 에서 이 한 권만 잡히는 것 확인, 2026-11-03).
실행:  python -m scripts.check_suzokwan
"""
import pandas as pd

from src import yes24

ITEM_ID = "124235834"
days = pd.date_range("2024-01-08", "2024-09-30", freq="W-MON")
print("날짜         순위 (1001 = 1000위 밖, None = 그날 데이터 없음). 캐시만 읽음")
for d in days:
    r = yes24.find_rank(d.strftime("%Y-%m-%d"), item_id=ITEM_ID, max_rank=1000)  # 11-03에 받은 1000위 캐시 확인용
    bar = "" if r is None or r == 1001 else "#" * max(1, (1001 - r) // 25)
    print(f"{d:%Y-%m-%d}  {str(r):>5}  {bar}")
