# 마스터 테이블 컬럼 사전 (master, 96,204행 × 26컬럼)

주문 1건 = 1행. 파일: `data/processed/master.parquet` (DuckDB `master` 테이블). 모집단은 분석기간(2017-01 ~ 2018-08) 중 도착일이 있는 주문(base). 2단계 모집단은 `low`가 NULL이 아닌 95,561건.

**[2026-09-30 추가] Day 5에서 파생변수 4개(`seller_avg_delay`, `seller_avg_delay_is_fallback`, `category_grouped`, `distance_km_filled`)를 추가해 `data/processed/master_features.parquet`(96,204행 × 30컬럼)로 별도 저장함. 이 문서의 "역할 구분" 표와 아래 컬럼 목록은 이 파생변수들까지 포함해 갱신됨 — Day 6부터는 master.parquet이 아니라 master_features.parquet을 읽을 것. (초기 저장본은 분석 중간 산출물인 `delivery_error_days`·`seller_id`가 함께 저장돼 32컬럼이었으나, 둘 다 최종 저장 전 drop하도록 05 노트북을 수정해 30컬럼으로 정리함, 05_seller_avg_delay_v14.ipynb — v13과 같은 결과임을 v14 전체 재실행으로 확인)**

**모집단 한계(D-18)**: "도착일이 있는 주문"만 다루므로, 분석기간 내 도착일이 없는 주문 2,888건(99,092건의 2.9% — shipped·unavailable·canceled·processing·invoiced 등)은 구조적으로 제외됨. 배송 실패·취소처럼 가장 불만이 클 만한 사례가 모델 스코프 밖에 있다는 뜻이므로, 최종 보고서 한계 섹션에 반드시 명시할 것.

## 역할 구분

| 역할 | 컬럼 |
|---|---|
| 식별 | `order_id`, `customer_id` |
| Y | `late`(1단계), `low`(2단계) |
| 1·2단계 공통 X (D-16 STAGE1, Day 5 파생, master에는 없음) | `distance_km_filled`(+`dist_missing`), `category_grouped`, `seller_avg_delay`(+`seller_avg_delay_is_fallback`) |
| 2단계 전용 X 추가 (D-16 STAGE2) | `price_sum`, `freight_sum`, `installments_max` |
| 보조 (파생변수 계산 중간산출물·추적용, 모델 입력 금지) | `customer_state`, `seller_state`, `category_en`, `category_pt`, `seller_by_price`, `seller_rep`, `distance_km`(원본), `n_items`, `n_sellers`, `order_approved_at` |
| **분할 기준 (모델 입력 금지)** | `purchase_ts` |
| **입력 금지 — 사후 정보** | `order_delivered_customer_date`, `order_status`, `review_id`, `review_score`, `review_comment_message` |
| **입력 금지 — 계획서 결정으로 제외** | `order_estimated_delivery_date` |
| **입력 금지 — Y와 직결** | `delivery_error_days` |
| **입력 금지 — 계획서 대비 변경(D-15 미사용 확정)** | `purchase_month` |
| EDA 전용 파생 (주문 단위, Day 4 계산, 모델 입력 금지) | 배송오차(도착일 − 예상도착일), 예상소요일(예상도착일 − 구매일) |
| Day 5 파생 X 최종 확정 (D-01, master에는 없음) | `seller_avg_delay`: 구매시각 이전에 "배송이 이미 끝난" 같은 셀러 주문만의 `late` 누적평균(0~1 비율이며 지연 일수가 아님, 시간순 causal, min_n=20 미만이면 같은 기준 전역평균 대체). 최초엔 "학습 구간 기준 + leave-one-out"으로 계획했으나 실제로는 시간순 causal 방식(구매시각 이전 배송완료분만)으로 구현·확정됨 — fold별 재계산이 불필요해짐(교차검증 구조와 무관하게 각 행이 자기 시점 기준으로 이미 causal함). 주문 단위 `late`·배송오차를 X로 넣는 것은 금지, 셀러 단위 과거 집계는 구매시각 이전에 배송이 끝난 주문만 쓰는 누수 차단 조건 아래에서만 허용. 상세 경과·한계는 decisions.md D-01 |

## 입력 금지 이유

두 종류를 구분한다. **① 완전한 사후 정보**(주문 시점에는 알 수 없고, 배송·리뷰 결과가 반영된 값)와 **② 계획서 결정으로 제외한 값**(주문 시점에 이미 알 수 있는 값이지만, Y 정의에 쓰이거나 계획서가 X에서 빼기로 결정한 값)은 성격이 다르므로 같은 표에 섞지 않는다.

### ① 완전한 사후 정보

| 컬럼 | 이유 |
|---|---|
| `order_delivered_customer_date` | **사후 정보**(배송 결과). Y 정의에도 쓰임 |
| `order_status` | 사후 정보(결과 상태가 반영됨) |
| `review_id`, `review_score`, `review_comment_message` | 사후 정보. 2단계 Y 자체이거나 3단계 분석용 리뷰 내용 |

### ② 계획서 결정으로 제외

| 컬럼 | 이유 |
|---|---|
| `order_estimated_delivery_date` | **Y(late) 정의에 쓰임.** 주문 시점에 이미 알려진 값이라 엄밀한 의미의 사후 정보는 아니지만(2단계 조기경보 관점에서는 오히려 쓸 수 있는 정보), Y 계산에 직접 쓰이는 값을 X로 같이 넣으면 안 된다는 이유로 계획서가 X에서 제외하기로 결정함. "포함하면 성능이 어떻게 달라지는가"는 한계/부록에서 별도로 비교할 수 있음(계획 변경 없이) |
| `purchase_ts` | **시간 분할 기준으로만 사용.** 테스트 구간의 `purchase_ts` 값은 정의상 학습 구간의 값보다 항상 큼(미래 시점). 이 값 자체를 X로 넣으면 모델이 "테스트 구간에서 한 번도 본 적 없는 값 범위"를 외삽해야 하고, 애초에 시간 기준으로 학습/테스트를 나눈 취지(미래 정보를 모델이 직접 보지 않게 하는 것)와도 어긋남 |

## 컬럼 목록

| 컬럼 | 역할 | 정의 | 특이사항 |
|---|---|---|---|
| `order_id` | 식별 | 주문 ID | 유일(96,204) |
| `customer_id` | 식별 | 주문마다 발급되는 고객 키 | `customer_unique_id`와 다름 |
| `order_status` | 입력 금지 | 주문 상태 | base는 이 컬럼이 아니라 도착일 유무로 정의되어, `canceled`인데 도착일이 있는 예외 1건(2018-02-19 주문)이 base에 포함됨. late=1로 계산됨(D-00) |
| `purchase_ts` | 분할 기준(입력 금지) | 구매 시각 | 시간 기준 분할(테스트 기간)에만 사용 |
| `purchase_month` | 입력 금지(미사용) | 구매 월(1~12) | 연도가 빠져 계절성과 추세가 섞임. D-15로 미사용 확정(06 노트북: 달력월 풀링에서는 1~3월·11월이 튀지만 연도별로 나누면 2017은 11월, 2018은 2~3월로 시점이 달라 반복 계절성으로 보기 어려움). 계획서 X 목록에 있던 변수라 계획 변경에 해당 |
| `order_approved_at` | 보조 | 승인 시각 | 2단계 예측 시점의 기준. **base(96,204건) 안에서 결측 14건** |
| `order_delivered_customer_date` | 입력 금지 | 고객 도착일 | |
| `order_estimated_delivery_date` | 입력 금지 | 예상도착일 | Y(late) 정의에 쓰임. 계획서 결정으로 X 제외(사후 정보라서가 아님) — 위 "입력 금지 이유 ②" 참고 |
| `late` | Y(1단계) | 도착일(날짜) > 예상도착일(날짜)이면 1 | `base.late`를 그대로 사용. 6,532건(6.79%) |
| `low` | Y(2단계) | `review_score` ≤ 2이면 1 | 리뷰 없으면 NULL(643건). 12,228건(리뷰 있는 95,561건의 12.8%) |
| `customer_state` | 보조 | 고객 주 | `distance_km_filled`의 대체값 계산에만 사용(D-04), 모델 입력 아님 |
| `seller_state` | 보조 | 대표 셀러(`seller_rep`)의 주 | |
| `price_sum` | 2단계 X | 주문 내 아이템 가격 합 | order_payments 실제 결제총액과 0.25%(241건)만 1원 넘게 차이남, 대부분 할부이자로 설명됨 — 실결제액 대리변수로 문제없음(D-19) |
| `freight_sum` | 2단계 X | 주문 내 배송비 합 | |
| `n_items` | 보조 | 아이템 수 | 계획서 X 목록에 없음 |
| `n_sellers` | 보조 | 셀러 수 | 멀티셀러 1,272건(1.32%) |
| `installments_max` | 2단계 X | 결제 회차 최댓값 | 범위 0~24, 0값 2건은 원본 유지(D-06) |
| `category_en` | 보조(입력 금지, `category_grouped`의 원천) | 대표 카테고리(가격이 가장 큰 아이템) | 원본 결측·번역표에 없으면 '미상'(1,376건). 상위 22개 묶음은 `category_grouped`로 파생(D-02). 대표화로 카테고리가 실제와 달라질 수 있는 주문은 778건(0.81%, 그중 싱글셀러는 182건)로 확인됨(D-19) — Feature Importance 해석 시 이 한계 함께 명시 |
| `category_pt` | 보조 | 원본 포르투갈어 카테고리 | 결측 가능 |
| `seller_by_price` | 보조 | 가격이 가장 큰 아이템의 셀러 | D-05 재현용 |
| `seller_rep` | 보조(입력 금지, `seller_avg_delay` 계산 키) | 대표 셀러(거리가 가장 먼 아이템의 셀러) | 멀티셀러에서 거리가 동점이거나 전부 NULL(6건)이면 `order_item_id` 오름차순으로 정해져, 동점 방향에 따라 `seller_rep`이 바뀌는 주문이 143건(0.15%, `distance_km`은 불변)(D-12) |
| `distance_km` | 보조(입력 금지, 모델 입력은 `distance_km_filled`) | 대표 거리(거리가 가장 먼 아이템). 중앙값 대표좌표 기반 하버사인 | 전부 NULL인 477건이 NULL(D-12) |
| `dist_missing` | 1·2단계 공통 X(결측 더미) | `distance_km`이 NULL이면 1 | 477건 |
| `review_id` | 입력 금지 | 리뷰 ID | 3단계에서 리뷰 단위 중복 제거 키(D-00d). 리뷰 없으면 NULL |
| `review_score` | 입력 금지 | 리뷰 점수(1~5) | 리뷰 없으면 NULL(643건) |
| `review_comment_message` | 입력 금지 | 리뷰 코멘트 | 3단계 텍스트 분석용. 결측 많음 |
| `seller_avg_delay` | 1·2단계 공통 X | 구매시각 이전에 배송완료된 같은 셀러 주문의 late 누적평균(0~1), min_n=20 미만이면 같은 기준 전역평균 대체 | master.parquet엔 없음(Day 5 파생, D-01). 전체기간 기준 mean 0.0466, fallback 32.4%. 한계: 신호의 상당 부분이 시기 효과를 대리(fallback AUC 0.62 > non-fallback AUC 0.59, 학습기간 기준). 다만 fallback 집단은 구조적으로 신규·초반 셀러에 몰려 있어 이 비교에는 신규 셀러 효과가 섞여 있을 수 있음(D-01 한계 2) |
| `seller_avg_delay_is_fallback` | 1·2단계 공통 X(결측 더미) | 위 fallback 대체 적용 여부 | |
| `category_grouped` | 1·2단계 공통 X | 상위 22개(개별) + 미상(별도) + 기타(49개 묶음) | master.parquet엔 없음(Day 5 파생, D-02). 고유값 24개. 90% 커버율 기준(21개 89.46%, 22개 90.25%)으로 22 채택 |
| `distance_km_filled` | 1·2단계 공통 X | distance_km 결측 477건을 customer_state 학습기간 평균으로 대체한 값 | master.parquet엔 없음(Day 5 파생, D-04). dist_missing과 함께 사용. seller_state(SP 70.9% 쏠림) 대신 customer_state(SP 42.0%) 채택 |

## 마스터에 없는 원본 컬럼 (참고)

| 컬럼(원본) | 제외 이유 |
|---|---|
| `payment_type` | 계획서 X 후보에 없어 집계하지 않음(installments_max만 채택, D-06). 의도적 제외이며 성능·품질 문제 아님 — 필요해지면 LEFT JOIN 한 줄로 추가 가능 |
| `customer_unique_id` | 분석 단위가 주문(order)이라 주문마다 발급되는 `customer_id`를 씀. 고객 단위(재구매 등) 분석을 하게 되면 그때 별도로 끌어와야 함 |
