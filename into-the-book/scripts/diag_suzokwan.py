"""수족관 순위가 들쭉날쭉한 원인 진단.

1. 제목에 '수족관'이 '포함'되거나 저자에 '유래혁'이 있는 행을 전부 출력 (어떤 책이 잡혔는지)
2. 같은 날 국내도서 전체(001) 1000위에서도 찾아봄 (카테고리가 다른지)

실행:  python -m scripts.diag_suzokwan
"""
import pandas as pd

from src import yes24

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)

days = ["2024-01-29", "2024-03-18", "2024-06-10", "2024-07-22", "2024-07-29", "2024-08-05"]

print("=== 1. 소설/시/희곡(001001046)에서 '수족관' 포함 또는 저자 '유래혁' ===")
for d in days:
    df = yes24.fetch_day(d)
    hit = df[df["title"].str.contains("수족관", na=False) | df["author"].str.contains("유래혁", na=False)]
    print(f"\n{d}  (그날 {len(df)}위까지)")
    print(hit[["rank", "title", "author", "publisher", "publishDate", "itemId"]].to_string(index=False)
          if not hit.empty else "  없음")

print("\n=== 2. 국내도서 전체(001)에서 저자 '유래혁' ===")
for d in ["2024-07-22", "2024-07-29"]:
    df = yes24.fetch_day(d, category="001")
    hit = df[df["author"].str.contains("유래혁", na=False) | df["title"].str.contains("수족관", na=False)]
    print(f"\n{d}  (그날 {len(df)}위까지)")
    print(hit[["rank", "title", "author", "publisher", "itemId"]].to_string(index=False)
          if not hit.empty else "  없음")
