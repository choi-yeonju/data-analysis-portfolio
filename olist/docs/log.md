# 실험 로그 (olist)

## Day 0 — 환경 셋팅 (2026-09-19)
- 목적: 분석을 시작할 수 있는 프로젝트 환경을 만들고 GitHub에 안전하게 올릴 준비
- 한 일:
  - data-analysis-portfolio 저장소 안에 olist 폴더 생성, 폴더 구조(data/raw·interim·processed, notebooks, src, docs, outputs) 구성
  - kagglehub로 받은 CSV 9개를 data/raw에 복사
  - .gitignore에 olist/data/raw 등 추가 후 git check-ignore로 무시 확인
  - Python 3.13.9 가상환경(.venv) 생성, 라이브러리 설치(pandas 3.0.6, numpy 2.5.3, scipy 1.18.1, scikit-learn 1.9.1, duckdb 1.5.5 등), requirements.txt 저장
  - .vscode/settings.json으로 노트북 기준 폴더를 olist로 고정
  - 01_load_check.ipynb에서 orders shape (99441, 8) 확인
- 결과: 환경 정상 동작, 첫 커밋 완료
- 문제·시행착오:
  - .venv 활성화 시 PowerShell "스크립트를 실행할 수 없습니다" 오류 → Set-ExecutionPolicy -Scope CurrentUser RemoteSigned로 해결
  - CSV 복사 때 kagglehub 캐시 폴더 구조(olistbr/brazilian-ecommerce/versions/2)가 통째로 raw 안에 들어감 → CSV 9개만 raw 바로 아래로 옮기고 빈 폴더 삭제
  - settings.json을 만들려다 VS Code 전체 개인 설정(User settings.json)을 열어버림 → 프로젝트 전용 파일(olist/.vscode/settings.json, Workspace Settings)과 구분해서 새로 만듦
- 내일: DuckDB로 CSV 9개 등록, 행 수·결측 확인


## Day 1 — 적재·품질 확인 (2026-09-19 ~ 09-20)
- 목적: CSV 9개를 DuckDB에 등록하고 행 수·결측을 확인, 계획서(부록 B) 기준 수치를 내 SQL로 재현
- 한 일: 01_load_check.ipynb (DuckDB VIEW 등록 → 행 수 → 타입 → 결측 → 도착일 결측 원인 → 리뷰 중복 제거 → 지연율·저평점 재현). 마지막에 Restart & Run All로 재현 확인(실행 번호 1~12 연속, 에러 없음), 노트북 끝에 con.close() 추가
- 결과:
  - 행 수: orders 99,441 / order_items 112,650 / order_reviews 99,224 / order_payments 103,886 / customers 99,441 / sellers 3,095 / products 32,951 / geolocation 1,000,163 / cat_tr 71 (전부 일치)
  - 결측: orders(승인 시각 160건, 출고일 1,783건, 도착일 2,965건=3.0%), products(카테고리 등 610건=1.9%, 무게·크기 각 2건), order_reviews(제목 88.3%, 코멘트 58.7%). 그 외 테이블과 geolocation은 결측 없음
  - 우편번호 타입: customers·sellers·geolocation 모두 INTEGER
  - 부록 B 재현 10개 전부 일치:
    - 리뷰 중복 제거 후 98,673행 (초과 551행 제거)
    - 분석기간 주문 99,092 / 도착일 있는 주문 96,204 / 지연율 6.79%
    - 도착+리뷰 존재 95,561 / 저평점 12.8% / 코멘트 있음 40.5%
    - 저평점률: 지연 주문 62.4%, 비지연 주문 9.2%
    - 3단계 대상(지연 아님 & 저평점) 8,247건, 그중 코멘트 있음 6,449건
    - 멀티셀러 주문: order_items 전체 기준 1,278건(98,666건의 1.3%) / 분석 모집단(96,204건) 기준 1,272건(1.32%)
  - 배송완료 96,204건 중 리뷰가 없는 주문 643건 (chk에는 리뷰 있는 95,561건만 포함)
- 해석:
  - 도착일 결측 2,965건은 대부분 배송 중·취소·미가용 등 배송 미완료 주문. 예외로 delivered인데 도착일 없음 8건, canceled인데 도착일 있음 6건(전체 기간). 이 6건 중 분석기간 내는 1건뿐(나머지 5건은 2016-10 주문)
  - 지연 주문의 저평점률(62.4%)이 비지연(9.2%)의 약 6.8배로, 지연과 저평점은 강하게 연결됨
  - 그러나 전체 저평점 12,228건 중 지연 주문은 3,981건(약 33%)뿐. 지연을 완벽히 예측해도 저평점의 약 2/3는 지연과 무관하게 남음 → 3단계(리뷰 텍스트 분석)의 필요성을 숫자로 확인
  - 3단계 대상 8,247건 중 78%(6,449건)에 코멘트가 있어 텍스트 분석 자료는 충분
  - 저평점 비율 12.8%는 계획서의 14.7%(리뷰 테이블 전체 기준)와 모집단이 달라서 다른 값. 2단계 기저율은 12.8% 사용
- 코드 리뷰에서 나온 것(→ decisions.md 반영): 취소 주문 1건 처리(D-00), review_id 중복(D-00d), 우편번호 앞자리 0(D-00e), payment_installments 0값 2건(D-06), 마스터 테이블 구조(D-07), 모집단 정의 단일화(D-08), DuckDB 연결 관리(E-07)
- 문제·시행착오:
  - 결측 확인 함수(null_profile)가 결측 없는 테이블에서 "Empty DataFrame..."을 출력 → 빈 표 판단을 len(res)로 바꿔 "결측 없음"이 나오도록 수정 (숫자는 처음부터 정상)
  - 사전 대응: 우편번호가 CSV에서 따옴표로 감싸져 문자열로 읽히므로 read_csv에 types=INTEGER를 지정 (조인 키 타입 통일). 이 과정에서 앞자리 0이 사라지는 것은 조인에 무해하지만 알아둘 점(D-00e)
  - 멀티셀러 1.3%가 전체 기간 기준이라 분석 모집단 기준(1,272건)과 분모가 다름 → 주석과 기록에서 구분
  - DuckDB 파일 락: 다른 노트북 커널이 같은 파일을 열고 있으면 읽기 전용으로도 열리지 않음 → 노트북 끝에 con.close(), 새 노트북 전에 이전 커널 종료
  - 다른 AI 코드 리뷰 7건 중 일부는 DuckDB의 NULL 정렬을 잘못 가정(DESC에서 NULL이 앞으로 온다고 지적, 실제로는 NULLS LAST) → 지적 내용은 데이터로 확인한 뒤에 반영
- 내일(Day 2): Day 1 커널 종료 후 시작 → base 테이블(96,204행, 지연율 6.79%) → geolocation 진단(DESCRIBE, 위·경도 min/max, 유일 우편번호 개수) → 브라질 범위 밖 좌표 처리 → geo_rep → distance_km
 