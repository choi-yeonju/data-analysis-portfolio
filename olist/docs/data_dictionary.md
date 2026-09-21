# 마스터 테이블 컬럼 사전 (master, 96,204행 × 26컬럼)

주문 1건 = 1행. 파일: `data/processed/master.parquet` (DuckDB `master` 테이블). 모집단은 분석기간(2017-01 ~ 2018-08) 중 도착일이 있는 주문(base). 2단계 모집단은 `low`가 NULL이 아닌 95,561건.

## 역할 구분

| 역할 | 컬럼 |
|---|---|
| 식별 | `order_id`, `customer_id` |
| Y | `late`(1단계), `low`(2단계) |
| 1·2단계 공통 X 후보 | `distance_km`(+`dist_missing`), `category_en`, `purchase_month`, `seller_rep`(Day 6에 `seller_avg_delay`를 파생하는 키) |
| 2단계 전용 X 후보 | `price_sum`, `freight_sum`, `installments_max` |
| 보조 (미매칭 대체용·추적용, 모델 입력은 계획 변경이 필요) | `customer_state`, `seller_state`, `category_pt`, `seller_by_price`, `n_items`, `n_sellers`, `order_approved_at` |
| **분할 기준 (모델 입력 금지)** | `purchase_ts` |
| **입력 금지** | `order_delivered_customer_date`, `order_estimated_delivery_date`, `order_status`, `review_id`, `review_score`, `review_comment_message` |
| EDA 전용 파생 (주문 단위, Day 4 계산, 모델 입력 금지) | 배송오차(도착일 − 예상도착일), 예상소요일(예상도착일 − 구매일) |
| Day 6 파생 X (마스터에는 없음) | `seller_avg_delay`(+결측 더미). 학습 구간의 `late`를 셀러 단위로 집계한 지연 비율(학습 행은 자기 제외, 교차검증은 fold별 재계산, D-01). 값은 지연 일수가 아니라 0~1 비율. 주문 단위 `late`·배송오차를 X로 넣는 것은 금지, 셀러 단위 과거 집계는 누수 차단 조건 아래에서만 허용 |

## 입력 금지 이유

| 컬럼 | 이유 |
|---|---|
| `order_delivered_customer_date` | **사후 정보**(배송 결과). Y 정의에도 쓰임 |
| `order_estimated_delivery_date` | **Y 정의에 쓰임(계획서 결정)**. 주문 시점에 알려진 값이라 엄밀한 사후 정보는 아니지만, 계획서가 X에서 제외하기로 결정함 |
| `order_status` | 사후 정보(결과 상태가 반영됨) |
| `review_id`, `review_score`, `review_comment_message` | 사후 정보. 2단계 Y 자체이거나 3단계 분석용 리뷰 내용 |
| `purchase_ts` | **시간 분할 기준으로만 사용.** 시점 값을 X로 넣으면 테스트 구간 값이 학습 범위 밖이라 모델이 왜곡됨 |

## 컬럼 목록

| 컬럼 | 역할 | 정의 | 특이사항 |
|---|---|---|---|
| `order_id` | 식별 | 주문 ID | 유일(96,204) |
| `customer_id` | 식별 | 주문마다 발급되는 고객 키 | `customer_unique_id`와 다름 |
| `order_status` | 입력 금지 | 주문 상태 | |
| `purchase_ts` | 분할 기준(입력 금지) | 구매 시각 | 시간 기준 분할(테스트 기간)에만 사용 |
| `purchase_month` | 공통 X 후보 | 구매 월(1~12) | 연도가 빠져 계절성과 추세가 섞임. 정수/범주형/미사용은 Day 5~6에 결정(D-15) |
| `order_approved_at` | 보조 | 승인 시각 | 2단계 예측 시점의 기준. 결측 가능 |
| `order_delivered_customer_date` | 입력 금지 | 고객 도착일 | |
| `order_estimated_delivery_date` | 입력 금지 | 예상도착일 | |
| `late` | Y(1단계) | 도착일(날짜) > 예상도착일(날짜)이면 1 | `base.late`를 그대로 사용. 6,532건(6.79%) |
| `low` | Y(2단계) | `review_score` ≤ 2이면 1 | 리뷰 없으면 NULL(643건). 12,228건(리뷰 있는 95,561건의 12.8%) |
| `customer_state` | 보조 | 고객 주 | 미매칭 대체(동일 주 평균) 후보 |
| `seller_state` | 보조 | 대표 셀러(`seller_rep`)의 주 | |
| `price_sum` | 2단계 X | 주문 내 아이템 가격 합 | |
| `freight_sum` | 2단계 X | 주문 내 배송비 합 | |
| `n_items` | 보조 | 아이템 수 | 계획서 X 목록에 없음 |
| `n_sellers` | 보조 | 셀러 수 | 멀티셀러 1,272건(1.32%) |
| `installments_max` | 2단계 X | 결제 회차 최댓값 | 범위 0~24, 0값 2건은 원본 유지(D-06) |
| `category_en` | 공통 X 후보 | 대표 카테고리(가격이 가장 큰 아이템) | 원본 결측·번역표에 없으면 '미상'(1,376건). 상위 N 묶음은 Day 5(D-02) |
| `category_pt` | 보조 | 원본 포르투갈어 카테고리 | 결측 가능 |
| `seller_by_price` | 보조 | 가격이 가장 큰 아이템의 셀러 | D-05 재현용 |
| `seller_rep` | 공통 X의 키 | 대표 셀러(거리가 가장 먼 아이템의 셀러) | 멀티셀러에서 거리가 동점이거나 전부 NULL(6건)이면 `order_item_id` 오름차순으로 정해져, 동점 방향에 따라 `seller_rep`이 바뀌는 주문이 143건(0.15%, `distance_km`은 불변)(D-12) |
| `distance_km` | 공통 X 후보 | 대표 거리(거리가 가장 먼 아이템). 중앙값 대표좌표 기반 하버사인 | 전부 NULL인 477건이 NULL(D-12) |
| `dist_missing` | 공통 X 후보(결측 더미) | `distance_km`이 NULL이면 1 | 477건 |
| `review_id` | 입력 금지 | 리뷰 ID | 3단계에서 리뷰 단위 중복 제거 키(D-00d). 리뷰 없으면 NULL |
| `review_score` | 입력 금지 | 리뷰 점수(1~5) | 리뷰 없으면 NULL(643건) |
| `review_comment_message` | 입력 금지 | 리뷰 코멘트 | 3단계 텍스트 분석용. 결측 많음 |
