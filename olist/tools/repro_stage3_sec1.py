"""3단계 §1 숫자 재현 (DuckDB). 실행: python tools/repro_stage3_sec1.py [data/raw 경로]
기대값: 8,247(5,884/2,363), 코멘트 6,449/1,798(review_id 1,787), 6,449->6,400, 짝 주문 93(48/18/27, dedup 후 리뷰표 기준)"""
import duckdb, sys
R=sys.argv[1] if len(sys.argv)>1 else "data/raw"
con=duckdb.connect()
con.execute(f"""
CREATE VIEW orders AS SELECT * FROM read_csv_auto('{R}/olist_orders_dataset.csv');
CREATE VIEW rv_raw AS SELECT * FROM read_csv_auto('{R}/olist_order_reviews_dataset.csv');
-- 분석 모집단(D-00): 2017-01-01 ~ 2018-08-31 구매 + 도착일 있음
CREATE VIEW base AS
SELECT order_id, order_purchase_timestamp AS purchase_ts,
       CAST(order_delivered_customer_date AS DATE) > CAST(order_estimated_delivery_date AS DATE) AS late
FROM orders
WHERE CAST(order_purchase_timestamp AS DATE) BETWEEN DATE '2017-01-01' AND DATE '2018-08-31'
  AND order_delivered_customer_date IS NOT NULL;
-- 주문 단위 리뷰 dedup(D-00b)
CREATE VIEW rv AS
SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id
   ORDER BY review_answer_timestamp DESC, review_creation_date DESC, review_id ASC) rn FROM rv_raw) WHERE rn=1;
CREATE VIEW t AS
SELECT b.order_id, b.purchase_ts, b.late, r.review_id, r.review_score,
       (r.review_comment_message IS NOT NULL AND length(trim(r.review_comment_message))>0) AS has_comment
FROM base b JOIN rv r USING(order_id);
""")
q=lambda s: con.execute(s).fetchall()
assert q("select count(*) from rv_raw")[0][0]==99224, "리뷰 원본 행 수 불일치(CSV 읽기 오류 의심)"
assert q("select count(*) from base")[0][0]==96204, "분석 모집단 불일치"
assert q("select round(100*avg(late::int),2) from base")[0][0]==6.79, "late 정의 불일치"
print("base", q("select count(*) from base"), "late%", q("select round(100*avg(late::int),2) from base"))
print("low&late=0 주문:", q("select count(*) from t where not late and review_score<=2"))
print("  점수별:", q("select review_score,count(*) from t where not late and review_score<=2 group by 1 order by 1"))
print("  코멘트 있음/없음:", q("select has_comment,count(*),count(distinct review_id) from t where not late and review_score<=2 group by 1 order by 1"))
print("  코멘트 있음 점수별:", q("select review_score,count(*) from t where not late and review_score<=2 and has_comment group by 1 order by 1"))
print("  작성률 1점/2점:", q("select review_score, sum(has_comment::int), count(*), round(100.0*sum(has_comment::int)/count(*),1) from t where not late and review_score<=2 group by 1 order by 1"))
con.execute("CREATE VIEW tgt AS SELECT * FROM t WHERE not late and review_score<=2 and has_comment")
assert q("select count(*), count(distinct review_id) from tgt")==[(6449,6400)]
assert q("select count(*) from t where not late and review_score<=2")[0][0]==8247
assert q("select review_score,count(*) from t where not late and review_score<=2 group by 1 order by 1")==[(1,5884),(2,2363)]
assert q("select has_comment,count(*),count(distinct review_id) from t where not late and review_score<=2 group by 1 order by 1")==[(False,1798,1787),(True,6449,6400)]
print("대상 주문/고유 review_id:", q("select count(*), count(distinct review_id) from tgt"))
print("중복 review_id(대상 안):", q("select count(*), sum(c) from (select review_id,count(*) c from tgt group by 1 having count(*)>1)"))
# 짝 주문: 대상 6,400 review_id 가 전체 주문(원본 리뷰표, dedup 전/후)에서 2개 이상 주문에 붙는 수
for name,src in [("원본 리뷰표(dedup 전)","rv_raw"),("dedup 후","rv")]:
    con.execute(f"""CREATE OR REPLACE VIEW pairs AS
    SELECT review_id, COUNT(DISTINCT order_id) n_orders FROM {src}
    WHERE review_id IN (SELECT review_id FROM tgt) GROUP BY 1""")
    n93=q("select count(*) from pairs where n_orders>=2")[0][0]
    con.execute(f"""CREATE OR REPLACE VIEW pcls AS
    SELECT p.review_id,
      MAX(CASE WHEN x.order_id IS NULL THEN 1 ELSE 0 END) AS has_out_of_base,
      MAX(CASE WHEN x.late THEN 1 ELSE 0 END) AS has_late1
    FROM (SELECT review_id, order_id FROM {src} WHERE review_id IN (SELECT review_id FROM pairs WHERE n_orders>=2)) p
    LEFT JOIN base x ON x.order_id=p.order_id GROUP BY 1""")
    # 우선순위: 분석 모집단 밖 짝 -> 27, late=1 짝 -> 18, 나머지(전부 대상 안 late=0) -> 48
    a=q("select count(*) from pcls where has_out_of_base=1")[0][0]
    b=q("select count(*) from pcls where has_out_of_base=0 and has_late1=1")[0][0]
    c=q("select count(*) from pcls where has_out_of_base=0 and has_late1=0")[0][0]
    print(f"[{name}] 2개 이상 주문에 붙은 review_id={n93}  | 모집단 밖 짝 {a} / late=1 짝(모집단 안) {b} / 전부 대상 안 {c}")
    if name=="dedup 후": assert (n93,a,b,c)==(93,27,18,48), (n93,a,b,c)
    a2=q("select count(*) from pcls where has_late1=1")[0][0]
    print(f"   (late=1 짝 전체, 밖 짝과 겹침 허용) {a2}")

print("모든 assert 통과: §1 기대값과 일치")
