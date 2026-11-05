# Into The Book

**어떤 검색 급증이 베스트셀러 진입을 예고하는가.** 2023~2024 출간 소설 전수를 대상으로 네이버 데이터랩 검색 급증 이벤트를 생존분석으로 추적해, 성과 지표 진입으로 이어지는 급증의 특징을 찾는다. **성과 지표(결과 변수) 소스는 재선정 중.**

> 진행 중 (파일럿 단계). 알라딘 OpenAPI가 2026-11-01 종료되어 YES24 Open API를 검토했으나, YES24가 1:1 문의에 "순위·상품 데이터의 수집·저장 불가"로 답해(2026-11-05) 사용하지 않는다. 파일럿 중 받은 YES24 점검용 캐시(2024년 월요일 39일)는 로컬에만 있으며 분석·게시에 쓰지 않고, 2026-11-19까지 삭제한다. 결과 변수는 공공 데이터(도서관 정보나루 등)로 재검토 중이며, 경위는 [PILOT_LOG.md](PILOT_LOG.md)에 있다. 원본 데이터는 커밋하지 않고 집계 결과만 공개한다. 판정 기준은 [PREREGISTRATION.md](PREREGISTRATION.md)에 데이터를 보기 전에 기록한다.

## 구조

```
into-the-book/
├── src/
│   ├── config.py        # .env 에서 API 키 읽기
│   ├── datalab.py       # 데이터랩 수집: 책 1권 = 요청 1회, 결측일 0, 일간 → 주간(월~일)
│   ├── yes24.py         # ⛔ 사용 중단 (YES24 수집 불허). 파일럿 기록·테스트용
│   ├── spikes.py        # 급증 판정: 직전 8주 z > 2 그리고 직전 6주 대비 배율 ≥ 2
│   └── event_study.py   # 진입 주 이벤트 스터디: 합산 비율 + 책 단위 부트스트랩
├── scripts/             # 파일럿 점검용 (결과는 PILOT_LOG.md)
│   ├── smoke_datalab.py     # 네이버 키 확인
│   ├── compare_keywords.py  # 키워드 구성 비교
│   ├── check_yes24*.py      # [보관용, 잠금] YES24 카테고리·시작일·깊이 확인
│   ├── check_suzokwan.py    # [보관용] 수족관 순위 추이 (캐시 삭제로 재실행 불가)
│   ├── diag_suzokwan.py     # [보관용] 수족관 매칭 진단
│   └── diag_cache.py        # [보관용] 짧은 페이지·salePoint 점검
├── tests/
├── PREREGISTRATION.md   # 데이터 보기 전에 정한 기준
├── PILOT_LOG.md         # 파일럿 발견 기록 (날짜순)
├── results/             # 공개용 집계 결과 (data/ 는 커밋 안 함)
└── .env.example
```

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env          # 값 채우기 (.env 는 커밋되지 않음)
python -m pytest -q
python -m scripts.smoke_datalab   # ⚠️ 키워드 규칙 확정 전에는 빈 응답
```

받은 응답은 `data/raw/datalab/` 에 캐시되고(커밋 안 됨), 하루 호출 수는 `data/raw/_datalab_calls.json` 에 기록되어 1,000회를 넘기기 전에 멈춘다.

## 설계 메모

- 여러 책을 한 요청에 넣지 않는다. 데이터랩은 요청 안 최댓값을 100으로 맞추므로 작은 책이 눌린다.
- 급증 판정에 절대 크기 조건(예: ratio ≥ 5)을 쓰지 않는다. 단독 요청에서 100은 보통 진입 후 피크라 미래 정보가 된다.
- z-score는 이번 주를 뺀 **직전** 8주로 계산한다. 이번 주를 포함하면 z의 최댓값이 (8−1)/√8 ≈ 2.47로 묶인다.
