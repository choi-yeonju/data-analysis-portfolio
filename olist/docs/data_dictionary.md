# 마스터 테이블 컬럼 사전 (master, 96,204행 × 26컬럼)

주문 1건 = 1행. 파일: `data/processed/master.parquet` (DuckDB `master` 테이블). 모집단은 분석기간(2017-01 \~ 2018-08) 중 도착일이 있는 주문(base). 2단계 모집단은 `low`가 NULL이 아닌 95,561건.

**[2026-09-30 추가] Day 5에서 파생변수 4개(`seller_avg_delay`, `seller_avg_delay_is_fallback`, `category_grouped`, `distance_km_filled`)를 추가해 `data/processed/master_features.parquet`(96,204행 × 30컬럼)로 별도 저장함. 이 문서의 "역할 구분" 표와 아래 컬럼 목록은 이 파생변수들까지 포함해 갱신됨 — Day 6부터는 master.parquet이 아니라 master_features.parquet을 읽을 것. (초기 저장본은 분석 중간 산출물인 `delivery_error_days`·`seller_id`가 함께 저장돼 32컬럼이었으나, 둘 다 최종 저장 전 drop하도록 05 노트북을 수정해 30컬럼으로 정리함, 05_seller_avg_delay.ipynb — 이전 버전과 같은 결과임을 전체 재실행으로 확인)**

**모집단 한계(D-18)**: "도착일이 있는 주문"만 다루므로, 분석기간 내 도착일이 없는 주문 2,888건(99,092건의 2.9% — shipped·unavailable·canceled·processing·invoiced 등)은 구조적으로 제외됨. 배송 실패·취소처럼 가장 불만이 클 만한 사례가 모델 스코프 밖에 있다는 뜻이므로, 최종 보고서 한계 섹션에 반드시 명시할 것.

## 역할 구분

| 역할 | 컬럼 |
|---|---|
| 식별 | `order_id`, `customer_id` |
| Y | `late`(1단계), `low`(2단계) |
| 1·2단계 공통 X (D-16 STAGE1. `dist_missing`은 03에서 master에 포함, 나머지는 Day 5 파생으로 master_features에만 있음) | `distance_km_filled`(+`dist_missing`), `category_grouped`, `seller_avg_delay`(+`seller_avg_delay_is_fallback`) |
| 2단계 전용 X 추가 (D-16 STAGE2) | `price_sum`, `freight_sum`, `installments_max` |
| 보조 (파생변수 계산 중간산출물·추적용, 모델 입력 금지) | `customer_state`, `seller_state`, `category_en`, `category_pt`, `seller_by_price`, `seller_rep`, `distance_km`(원본), `n_items`, `n_sellers`, `order_approved_at` |
| **분할 기준 (모델 입력 금지)** | `purchase_ts` |
| **입력 금지 — 사후 정보** | `order_delivered_customer_date`, `order_status`, `review_id`, `review_score`, `review_comment_message` |
| **입력 금지 — 계획서 결정으로 제외** | `order_estimated_delivery_date` |
| **입력 금지 — Y와 직결** | `delivery_error_days` |
| **입력 금지 — 계획서 대비 변경(D-15 미사용 확정)** | `purchase_month` |
| EDA 전용 파생 (주문 단위, Day 4 계산, 모델 입력 금지) | 배송오차(도착일 − 예상도착일), 예상소요일(예상도착일 − 구매일) |
| Day 5 파생 X 최종 확정 (D-01, master에는 없음) | `seller_avg_delay`: 구매시각 이전에 "배송이 이미 끝난" 같은 셀러 주문만의 `late` 누적평균(0\~1 비율이며 지연 일수가 아님, 시간순 causal, min_n=20 미만이면 같은 기준 전역평균 대체). 최초엔 "학습 구간 기준 + leave-one-out"으로 계획했으나 실제로는 시간순 causal 방식(구매시각 이전 배송완료분만)으로 구현·확정됨 — fold별 재계산이 불필요해짐(교차검증 구조와 무관하게 각 행이 자기 시점 기준으로 이미 causal함). 주문 단위 `late`·배송오차를 X로 넣는 것은 금지, 셀러 단위 과거 집계는 구매시각 이전에 배송이 끝난 주문만 쓰는 누수 차단 조건 아래에서만 허용. 상세 경과·한계는 decisions.md D-01 |

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
| `purchase_month` | 입력 금지(미사용) | 구매 월(1\~12) | 연도가 빠져 계절성과 추세가 섞임. D-15로 미사용 확정(06 노트북: 달력월 풀링에서는 1\~3월·11월이 튀지만 연도별로 나누면 2017은 11월, 2018은 2\~3월로 시점이 달라 반복 계절성으로 보기 어려움). 07 5절 ablation에서도 PR-AUC·ROC-AUC 변화가 ±0.01 이내. 계획서 X 목록에 있던 변수라 계획 변경에 해당 |
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
| `installments_max` | 2단계 X | 결제 회차 최댓값 | 범위 0\~24, 0값 2건은 원본 유지(D-06) |
| `category_en` | 보조(입력 금지, `category_grouped`의 원천) | 대표 카테고리(가격이 가장 큰 아이템) | 원본 결측·번역표에 없으면 '미상'(1,376건). 상위 22개 묶음은 `category_grouped`로 파생(D-02). 대표화로 카테고리가 실제와 달라질 수 있는 주문은 778건(0.81%, 그중 싱글셀러는 182건)로 확인됨(D-19) — 카테고리를 모델 해석(계수·permutation 중요도)에 쓸 때 이 한계 함께 명시(1단계 Feature Importance 해석은 하지 않음, D-36) |
| `category_pt` | 보조 | 원본 포르투갈어 카테고리 | 결측 가능 |
| `seller_by_price` | 보조 | 가격이 가장 큰 아이템의 셀러 | D-05 재현용 |
| `seller_rep` | 보조(입력 금지, `seller_avg_delay` 계산 키) | 대표 셀러(거리가 가장 먼 아이템의 셀러) | 멀티셀러에서 거리가 동점이거나 전부 NULL(6건)이면 `order_item_id` 오름차순으로 정해져, 동점 방향에 따라 `seller_rep`이 바뀌는 주문이 143건(0.15%, `distance_km`은 불변)(D-12) |
| `distance_km` | 보조(입력 금지, 모델 입력은 `distance_km_filled`) | 대표 거리(거리가 가장 먼 아이템). 중앙값 대표좌표 기반 하버사인 | 전부 NULL인 477건이 NULL(D-12) |
| `dist_missing` | 1·2단계 공통 X(결측 더미) | `distance_km`이 NULL이면 1 | 477건 |
| `review_id` | 입력 금지 | 리뷰 ID | 3단계에서 리뷰 단위 중복 제거 키(D-00d). 리뷰 없으면 NULL |
| `review_score` | 입력 금지 | 리뷰 점수(1\~5) | 리뷰 없으면 NULL(643건) |
| `review_comment_message` | 입력 금지 | 리뷰 코멘트 | 3단계 텍스트 분석용. 결측 많음 |
| `seller_avg_delay` | 1·2단계 공통 X | 구매시각 이전에 배송완료된 같은 셀러 주문의 late 누적평균(0\~1), min_n=20 미만이면 같은 기준 전역평균 대체 | master.parquet엔 없음(Day 5 파생, D-01). 전체기간 기준 mean 0.0466, fallback 32.4%. 한계: 신호의 상당 부분이 시기 효과를 대리(fallback AUC 0.62 > non-fallback AUC 0.59, 학습기간 기준). 다만 fallback 집단은 구조적으로 신규·초반 셀러에 몰려 있어 이 비교에는 신규 셀러 효과가 섞여 있을 수 있음(D-01 한계 2). Day 6 진단(07): fallback 행 월 내 AUC 0.514(합산 0.624)로 시기 효과 확인, 시기를 걷어낸 non-fallback 월 내 AUC는 학습 0.561 / 테스트 0.545, 초반 값은 배송완료분만 쓰는 규칙으로 실제 누적보다 낮게 편향(최대 약 0.027). D-01 한계 3 |
| `seller_avg_delay_is_fallback` | 1·2단계 공통 X(결측 더미) | 위 fallback 대체 적용 여부 | |
| `category_grouped` | 1·2단계 공통 X | 상위 22개(개별) + 미상(별도) + 기타(49개 묶음) | master.parquet엔 없음(Day 5 파생, D-02). 고유값 24개. 90% 커버율 기준(21개 89.46%, 22개 90.25%)으로 22 채택 |
| `distance_km_filled` | 1·2단계 공통 X | distance_km 결측 477건을 customer_state 학습기간 평균으로 대체한 값 | master.parquet엔 없음(Day 5 파생, D-04). dist_missing과 함께 사용. seller_state(SP 70.9% 쏠림) 대신 customer_state(SP 42.0%) 채택 |

## 마스터에 없는 원본 컬럼 (참고)

| 컬럼(원본) | 제외 이유 |
|---|---|
| `payment_type` | 계획서 X 후보에 없어 집계하지 않음(installments_max만 채택, D-06). 의도적 제외이며 성능·품질 문제 아님 — 필요해지면 LEFT JOIN 한 줄로 추가 가능 |
| `customer_unique_id` | 분석 단위가 주문(order)이라 주문마다 발급되는 `customer_id`를 씀. 고객 단위(재구매 등) 분석을 하게 되면 그때 별도로 끌어와야 함 |

## 07·08 산출물 (Day 6)

모델 입력 컬럼 정의는 위와 같고(master_features.parquet 96,204행 × 30컬럼을 07·08이 읽음), 아래는 07 7-10 셀과 08이 만드는 파일이다.

### data/processed/07_outputs/ (07 7-10 셀이 생성, .gitignore 대상이라 07을 다시 돌려 재생성)

| 파일 | 내용 |
|---|---|
| `preds_stage1.parquet` | 1단계 테스트 구간 예측. `order_id`, `y`(late), `prob_logit`, `prob_rf` (25,352행, 07의 `te1` 순서) |
| `preds_stage2.parquet` | 2단계 테스트 구간 예측. 같은 컬럼, y는 low (25,242행, `te2` 순서) |
| `meta.json` | 모델 4개별 선택 설정(`selected`), F1 임계값(`thr`), 테스트 `pr_auc`, `base_rate`, `n_test` |
| `cv_results.csv` | 07 7-3·7-5의 `cv_results`(선택 설정 이름, 임계값, PR-AUC, 상위 10% lift 등) |

### outputs/tables/ (08 5-1 셀이 생성, 테스트 결과를 본 뒤의 사후 지표 포함)

| 파일 | 컬럼 |
|---|---|
| `results.csv` (단계×모델 4행) | `단계`, `모델`(logit/rf), `선택 설정`, `n_test`, `양성 기저율`, `PR-AUC`, `PR-AUC/기저율`, `F1 임계값`, `top5_/top10_` + `precision`·`lift`(= precision ÷ 기저율)·`captured`(전체 양성 중 경보에 잡힌 비율), `섞은라벨_평균비율`(학습 라벨 5회 섞은 뒤 테스트 PR-AUC/기저율 평균), `학습_in-sample_비율`, `더미_accuracy`(항상 음성 예측) |
| `results_monthly.csv` | `단계`, `모델`, `월`, `n`, `양성`, `기저율`, `PR-AUC`, `PR-AUC/기저율`(월 안에서 계산, 양성 0이면 NaN) |
| `perm_importance_last_fold.csv` | `단계`, `모델`, `변수`, `기준 PR-AUC/기저율`, `하락(PR-AUC/기저율)`, `표준편차`(학습 구간 마지막 검증 fold, 10회 반복, 보조·사후) |

`results.csv`에는 07의 7-7 기준선(R0·R1)과 부트스트랩 구간, 7-9 민감도, 7-8 VIF가 들어 있지 않다. 기준선과 민감도는 decisions.md D-21, VIF는 log.md Day 6 참고.

### outputs/figures/
`08_monthly_ratio.png`(월별 PR-AUC/기저율, 점 옆 숫자 = 월 양성 건수), `08_pr_curves.png`, `08_perm_importance.png`

## 3단계 산출물 (2026-10-29 추가)

`data/processed/`와 `data/interim/`는 README 기준 `.gitignore` 대상이고 원문·번역문이 든 파일은 올리지 않는다. `outputs/`, `tools/`, `docs/`는 git에 올린다. 아래는 코드와 커밋 기록으로 확인된 것만 적었고, 확인 못 한 열은 "확인 안 함"으로 둔다.

| 위치 | 파일 | 내용 |
|---|---|---|
| `data/processed/stage3/` | `stage3_sample_manifest.csv` | 층화 표본 310행 7열(`review_id, split, in_150, rank_in_stratum, label_order, stratum, weight_all`), sha256 `c4469f54…a606fb`. 커밋하지 않음(D-23, D-36), 10 노트북 재실행으로 재생성 |
| 〃 | `stage3_mapping.csv` | 표본 메타. 14열: `review_id, split, label_order, stratum, N_h, n_h, weight_all, weight_150, in_150, rank_in_stratum, answered_before_delivery, late_ts, is_aug_2018, is_jul_aug_2018`. 층 = 분기 × 점수(1·2점) 14개 |
| 〃 | `stage3_cross_vars_6400__open_after_labeling.csv` | 대상 6,400건의 교차 변수. 집계가 쓰는 열: `freight_sum, price_sum, n_items, n_sellers, freight_tercile, n_items_grp, n_sellers_grp`(그 외 열은 확인 안 함). **라벨링이 끝난 뒤에만 연다** |
| `data/processed/stage3/` | `stage3_label_times.csv`, `stage3_label_times_hold.csv` | 건별 라벨링 소요 시간(열 `saved_at, pass, ver, label_order, review_id, seconds, viewed_pt`, 원문·번역 없음). `viewed_pt` = 원문 보기 명령(`o`) 사용 여부 |
| `data/interim/stage3/` | `translations_dev.csv`, `translations_hold.csv` | 번역 캐시(원문·번역, 올리지 않음) |
| `outputs/labels/` | `stage3_labels_dev.csv` | dev 라벨(첫 라벨 204 + 재라벨 100 = 304행, D-32 기록 기준, 공식 라벨 선택은 D-34). 마지막 수정 10-26 13:05(파일 시각, 재라벨 내보내기 커밋 `3fbaecb`) 이후 변경 없음 |
| 〃 | `stage3_labels_hold.csv` | hold-out 106행(첫 라벨이 공식, review_id 106개, 결측 0, `codebook_ver`는 v1 하나, 원문 없음) |
| `outputs/tables/` | `stage3_holdout_rule_eval.csv`, `stage3_holdout_rule_confusion.csv` | hold-out 규칙 평가(`eval_hold.py`, 1회, 커밋 `875912e`) |
| 〃 | `stage3_results_shares.csv`, `_h3.csv`, `_cross.csv`, `_sensitivity.csv`, `_p6b_split.csv`, `_rule_weighted.csv` | **공식 집계**(`stage3_results.py`). `_sensitivity.csv`는 2026-10-30 규칙 문서 §8 방식으로 재계산(D-35) |
| 〃 | `stage3_final_shares.csv`, `_h3.csv`, `_cross.csv`, `_sensitivity_aug.csv`, `_p6b_split.csv` | 교차검증용 두 번째 구현(`report_stage3.py`). 비가중 건수 교차표와 H1 보조 지표는 여기에만 있다. 민감도는 공식 집계 값을 쓴다(D-34) |

공식 라벨 열(`label_hold.py --export` 코드 기준): `review_id, label_order, pass, label_main, label_sub, mentions_freight_cost, codebook_ver`. dev 파일의 열은 같은 형식으로 보이나 열 이름은 확인 안 함. 분석에서는 P9a·P9b를 P9로 합친다.
