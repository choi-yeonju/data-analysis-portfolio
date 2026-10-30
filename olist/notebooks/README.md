# notebooks — 노트북 안내

01 → 08, 그다음 11 순서로 실행한다(재현 방법은 프로젝트 README). 09·10은 3단계 표본을 뽑은 기록이라 다시 실행하지 않는다. 각 노트북 맨 위 표에 목적·입력·출력·관련 결정이 있고, 맨 아래 「결론」 셀에 최종 결과가 있다.

| 노트북 | 하는 일 | 입력 → 출력 | 관련 결정 |
|---|---|---|---|
| `01_load_check` | 원본 적재, 품질·모집단 확인 | raw CSV → `olist.duckdb` | D-00, D-00b, D-00c |
| `02_geo_distance` | 대표좌표, 거리, 분석 모집단(`base`), 우측절단 검증 | duckdb → `base`, `item_lvl` | D-04, D-09, D-10, D-17 |
| `03_master` | 주문 단위 마스터 | duckdb → `master.parquet`(96,204 × 26), `item_base.parquet` | D-05, D-06, D-12, D-13 |
| `04_eda` | 테스트 기간 결정, 필수 검정(T-test·카이제곱·상관·VIF) | `master.parquet` → (그림만) | D-03, D-17 |
| `05_seller_avg_delay` | 파생변수 확정, 입력 목록 고정 | `master.parquet` → `master_features.parquet`(96,204 × 30) | D-01, D-02, D-04, D-16 |
| `06_purchase_month` | purchase_month 미사용 판단 | `master.parquet` → (그림만) | D-15 |
| `07_baseline` | 1·2단계 모델, CV 튜닝, 베이스라인, 원인 진단 | `master_features.parquet` → `07_outputs/` | D-20, D-21 |
| `08_wrapup` | 07 결과의 사후 분석, 결과표·그림 | `07_outputs/` → `outputs/tables/`, `outputs/figures/` | D-21, D-22 |
| `09_stage3_step1_target` | 3단계 대상(비지연 저평점·코멘트 있음 6,400리뷰) 추출 **(재실행 안 함)** | `master_features.parquet`, 리뷰 CSV → `stage3_target_6400.parquet` | D-00d, D-23\~D-26 |
| `10_stage3_step2_sample` | 층화 표본 310건(dev 204 / hold-out 106) 추출 **(재실행 안 함)** | `stage3_target_6400.parquet` → `data/processed/stage3/`(manifest, dev/hold-out 파일) | D-27, D-28 |
| `11_stage3_results` | 3단계 결과 표·그림, 결과 문서와 assert 대조(kappa만 재계산) | `outputs/tables/stage3_results_*.csv`, 라벨 → `outputs/figures/11_*.png` | D-23\~D-35 |

## 읽을 때 알아둘 것
- **07의 2\~5절은 임시 고정값 모델**이다. 최종 결과는 07 7절, 원인 진단 근거 셀은 6-13, 사후 분석은 08.
- 3단계 집계는 `tools/` 스크립트가 하고(순서는 `docs/README_snippet.md`), 11은 그 결과를 읽어 보여 주기만 한다.
- 본문의 `[YYYY-MM-DD 정정·추가]`는 고친 이력이다. 지우지 않고 남겨 두었으며, 최종 판단은 각 노트북의 「결론」 셀과 `docs/decisions.md`를 따른다.
- 04의 "잠정" 표기는 작성 당시 기록이다(확정은 decisions D-03).
- 공통 정의(분할, 전처리, 그리드)는 `src/common.py`에 있고, 08 0절에서 07 결과와 일치하는지 assert로 확인한다.
