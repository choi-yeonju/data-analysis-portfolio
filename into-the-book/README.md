# Into The Book

**어떤 검색 급증이 베스트셀러 진입을 예고하는가.** 2023~2024 출간 소설 전수를 대상으로 네이버 데이터랩 검색 급증 이벤트를 생존분석으로 추적해, 알라딘 주간 소설 Top100 진입으로 이어지는 급증의 특징을 찾는다.

> 진행 중 (파일럿 단계). 판정 기준은 [PREREGISTRATION.md](PREREGISTRATION.md)에 데이터를 보기 전에 기록한다.

## 구조

```
into-the-book/
├── src/
│   ├── config.py        # .env 에서 API 키 읽기
│   ├── datalab.py       # 데이터랩 수집: 책 1권 = 요청 1회, 결측일 0, 일간 → 주간(월~일)
│   ├── spikes.py        # 급증 판정: 직전 8주 z > 2 그리고 직전 6주 대비 배율 ≥ 2
│   └── event_study.py   # 진입 주 이벤트 스터디: 합산 비율 + 책 단위 부트스트랩
├── scripts/
│   └── smoke_datalab.py # 키 확인 + 0단계 점검 (호출 2회)
├── tests/
├── PREREGISTRATION.md
└── .env.example
```

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env          # 값 채우기 (.env 는 커밋되지 않음)
python -m pytest -q
python -m scripts.smoke_datalab
```

받은 응답은 `data/raw/datalab/` 에 캐시되고(커밋 안 됨), 하루 호출 수는 `data/raw/_datalab_calls.json` 에 기록되어 1,000회를 넘기기 전에 멈춘다.

## 설계 메모

- 여러 책을 한 요청에 넣지 않는다. 데이터랩은 요청 안 최댓값을 100으로 맞추므로 작은 책이 눌린다.
- 급증 판정에 절대 크기 조건(예: ratio ≥ 5)을 쓰지 않는다. 단독 요청에서 100은 보통 진입 후 피크라 미래 정보가 된다.
- z-score는 이번 주를 뺀 **직전** 8주로 계산한다. 이번 주를 포함하면 z의 최댓값이 (8−1)/√8 ≈ 2.47로 묶인다.
