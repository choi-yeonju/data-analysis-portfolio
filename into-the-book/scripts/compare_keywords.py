"""3-3 키워드 규칙 점검: 어떤 키워드 구성에서 값이 나오는지 비교 (호출 6회).

계획서 4개 키워드 그룹이 빈 응답(전부 0)으로 와서, 제목만 넣은 경우와 나눠서 본다.
실행:  python -m scripts.compare_keywords
"""
from src import datalab

TITLE, AUTHOR = "여름은 고작 계절", "김서해"
START, END = "2025-06-01", "2025-09-30"

variants = {
    "제목만": [TITLE],
    "제목 + 4개 조합": [TITLE] + datalab.build_keywords(TITLE, AUTHOR),
    "제목 저자": [f"{TITLE} {AUTHOR}"],
    "저자 제목": [f"{AUTHOR} {TITLE}"],
    "제목 책": [f"{TITLE} 책"],
    "제목 소설": [f"{TITLE} 소설"],
}

print(f"{'구성':<14} {'응답 일수':>8} {'0 아닌 일수':>10} {'소수점':>6}")
for name, kw in variants.items():
    resp = datalab.fetch(f"kwtest_{name}", kw, START, END, time_unit="date")
    rows = resp["results"][0]["data"]
    nonzero = sum(1 for r in rows if float(r["ratio"]) > 0)
    dp = datalab.decimal_places(resp) if rows else "-"
    print(f"{name:<14} {len(rows):>8} {nonzero:>10} {dp:>6}")

print("\n요청 기간 일수:", len(datalab.to_daily(resp, START, END)))
print("오늘 호출 수:", datalab.calls_today())
