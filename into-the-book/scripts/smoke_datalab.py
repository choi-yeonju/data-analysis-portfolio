"""⚠️ build_keywords 는 아직 옛 규칙(빈 응답). 다시 돌리면 데이터랩 호출만 쓴다. 결과는 PILOT_LOG 참고.

키가 잘 붙었는지 + 0단계 확인용. 호출 2회 (일간 1, 주간 1).

실행 (into-the-book 폴더에서):  python -m scripts.smoke_datalab
"""
from src import datalab

BOOK_ID = "smoke_여름은고작계절"
TITLE, AUTHOR = "여름은 고작 계절", "김서해"
START, END = "2025-06-01", "2025-09-30"

kw = datalab.build_keywords(TITLE, AUTHOR)
print("키워드 그룹:", kw)

daily_resp = datalab.fetch(BOOK_ID, kw, START, END, time_unit="date")
weekly_resp = datalab.fetch(BOOK_ID, kw, START, END, time_unit="week")

daily = datalab.to_daily(daily_resp, START, END)
weekly_sum = datalab.daily_to_weekly(daily)
weekly_direct = datalab.to_weekly_direct(weekly_resp)

print("\n[0단계] 응답 소수점 자릿수:", datalab.decimal_places(daily_resp))
print("[0단계] 응답에서 빠진 날 수 (0으로 채움):", len(daily) - len(daily_resp["results"][0]["data"]))
print("[0단계] 주 시작 요일 (0=월):", sorted({d.weekday() for d in weekly_direct.index}))

print("\n일간 합 vs 주간 직접 요청 (스케일이 다르니 모양만 비교):")
cmp = weekly_sum.join(weekly_direct.rename("direct"), how="left")
cmp["sum_scaled"] = cmp["ratio"] / cmp["ratio"].max() * 100
print(cmp.round(2).to_string())

print("\n오늘 호출 수:", datalab.calls_today())
