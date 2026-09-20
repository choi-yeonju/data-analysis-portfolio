# 결정 로그 (olist)

## 환경·운영 결정
- E-01 위치·구조: data-analysis-portfolio/olist 안에서 작업. 근거: 포트폴리오를 한 저장소에 모으고 프로젝트별 폴더로 분리
- E-02 데이터 관리: 원본 CSV는 olist/data/raw에 두고 git에는 올리지 않음(.gitignore에 raw·interim·processed 추가). 근거: geolocation이 약 60MB이고 GitHub 파일 크기 제한(100MB)·저장소 용량 문제. 재현 방법: kagglehub.dataset_download("olistbr/brazilian-ecommerce")
- E-03 DuckDB 파일 위치: data/interim/olist.duckdb (계획서 초안의 data/olist.duckdb에서 변경). 근거: interim은 .gitignore 대상이라 실수로 커밋되지 않음
- E-04 노트북 경로 기준: .vscode/settings.json의 jupyter.notebookFileRoot = ${workspaceFolder}, VS Code에서 olist 폴더를 열어 작업. 근거: notebooks/ 안에서도 data/raw/... 짧은 경로를 쓰기 위해
- E-05 실행 환경: Python 3.13.9, olist/.venv, 패키지 버전은 requirements.txt로 고정
- E-06 SQL 도구: DuckDB 사용(설치 없이 CSV를 SQL로 조회). 근거: 계획서의 SQL 조인 요건을 서버 세팅 부담 없이 충족. 참고: read_csv, EXCLUDE는 DuckDB 전용 문법
- E-07 DuckDB 연결 관리: 노트북 마지막에 con.close()를 실행하고, 새 노트북을 열기 전에 이전 노트북 커널을 종료. 근거: DuckDB 파일은 다른 프로세스(다른 노트북 커널)가 열고 있으면 읽기 전용으로도 열리지 않음("Could not set lock on file"). 같은 프로세스 안에서 다시 연결하는 것은 문제없음

## 분석 결정 (계획서 규칙의 구현 기준)
### D-00 분석 모집단
- 분석기간 2017-01-01 ~ 2018-08-31 구매 주문 중 도착일(order_delivered_customer_date)이 있는 주문 (96,204건)
- delivered인데 도착일 없는 8건: 분석기간 내에서도 8건 전부 해당(분석기간 내 delivered 96,211건 중 도착일 있음 96,203건). 도착일 필터로 제외
- canceled인데 도착일 있는 6건(전체 기간) 중 분석기간 내는 1건(2018-02-19 주문, 리뷰 3점). 나머지 5건은 2016-10 주문이라 기간에서 제외
- 정합성: 분석 모집단 96,204건 = delivered(도착일 있음) 96,203건 + canceled(도착일 있음) 1건
- 결정: 도착일 유무 기준을 그대로 유지해 그 1건은 포함. 근거: 도착일이 기록돼 있고 리뷰까지 있어 실제로 받은 주문으로 판단. 규칙이 단순하고 영향은 1건(96,204건 중)

### D-00b 리뷰 중복 처리 (주문 단위)
- 한 주문에 리뷰가 여러 개면 review_answer_timestamp가 가장 최근인 1건만 사용. 동률이면 review_creation_date 최신, 그다음 review_id 오름차순(ASC)
- NULL 정렬: DuckDB 기본이 NULLS LAST이고 review_answer_timestamp의 NULL은 0건이라 영향 없음. 다른 DB(PostgreSQL 등)로 옮길 때는 NULLS LAST를 명시할 것
- 결과: 99,224행 → 98,673행 (초과 551행 제거, 리뷰가 2개 이상인 주문은 547개)

### D-00c 지연·저평점 정의
- 지연(late) = 도착일(날짜) > 예상도착일(날짜). 시각은 버리고 날짜만 비교(CAST AS DATE)
- 저평점(low) = review_score <= 2. 리뷰가 없는 주문은 low를 0이 아니라 NULL로 둠(저평점 비율 왜곡 방지)
- 01_load_check의 chk 테이블은 2단계 확인용이라 INNER JOIN(리뷰 있는 95,561건만). 리뷰 없는 643건이 빠지므로 1단계 모집단(96,204건)으로 쓰지 않음. 마스터 테이블(Day 3)은 LEFT JOIN + low NULL로 따로 만듦
- 2단계 기저율은 모집단(분석기간·배송완료·리뷰 1건) 기준 12.8% 사용. 계획서의 14.7%는 리뷰 테이블 전체 기준

### D-00d review_id 중복 (3단계용)
- 원본에서 같은 review_id가 서로 다른 order_id 여러 개에 붙어 있음: 789개 review_id (2개 주문 764개, 3개 주문 25개, 초과 814행). 점수·코멘트는 동일
- D-00b는 order_id 기준 dedup이라 이 중복은 남음: 주문 단위 dedup 후에도 561개 review_id가 1,139개 주문에 걸침
- 3단계 영향: 코멘트 있는 대상 6,449주문 → 고유 review_id 6,400건(약 0.8%). 지연율·저평점률 같은 주문 단위 수치에는 영향 없음
- 결정 예정: 3단계 표본 추출·키워드 집계는 review_id 기준으로 중복 제거 (분석 단위를 주문이 아니라 리뷰로)

### D-00e 우편번호 처리
- 원본은 항상 5자리 문자열이고 앞자리 0으로 시작하는 값이 많음(sellers 1,027행, customers 23,995행). read_csv에서 INTEGER로 지정하면 앞자리 0이 사라짐 (예: "01037" → 1037)
- customers·sellers·geolocation을 모두 INTEGER로 통일해 조인에는 문제없음. 위험한 건 문자열과 정수가 섞이는 경우
- 지도 시각화나 외부 우편번호 자료와 합칠 때만 LPAD(CAST(zip AS VARCHAR), 5, '0')로 복원

## 확정 대기 (계획서상 1주차 확정 항목, Day 5 예정)
- D-01 seller_avg_delay 최소 주문 건수(min_n): 후보별 커버 셀러 수·주문 비율·추정 오차 표 후 결정
- D-02 카테고리 상위 N: 누적 커버율 표 후 결정
- D-03 테스트 기간: 월별 지연율·저평점률 추이 확인 후 결정 (결정 후 변경 금지)
- D-04 geolocation 미매칭 비중 확인 및 처리(동일 주 평균 + 결측 더미, 평균은 학습 구간 기준). Day 1 확인: geolocation 1,000,163행, 결측 없음
- D-05 멀티셀러 주문에서 대표 아이템 기준(가격 vs 거리) 일치율 확인. 계산 대상은 분석 모집단(96,204건) 기준 멀티셀러 1,272건(1.32%). order_items 전체 기준은 1,278건(1.3%) (01_load_check.ipynb [검증 1]로 재현)
- D-06 payment_installments 0값 처리 (Day 3): credit_card 2건이 0이고, 두 주문 모두 결제 행이 그 한 건뿐이라 주문 단위 MAX도 0. 결측처럼 볼지 정하고, 분석 모집단 포함 여부도 확인
- D-07 마스터 테이블 구조 (Day 3): LEFT JOIN + low NULL 단일 테이블(1단계는 96,204건 전체, 2단계는 low IS NOT NULL인 95,561건)로 갈지 확정
- D-08 모집단 정의 단일화 (Day 2): base 테이블(96,204행, 지연율 6.79%)을 만들고, 이후 모든 SQL은 base 기준으로 사용