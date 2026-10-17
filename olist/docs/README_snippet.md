## 재현 방법

환경: Python 3.13.9, `olist/.venv` (E-05). VS Code에서 `olist` 폴더를 열어 작업한다(노트북 경로 기준이 프로젝트 루트, E-04).

1. 패키지 설치: `pip install -r requirements.txt`
2. 원본 데이터: `data/raw/`에 Olist CSV 9개를 **하위 폴더 없이 바로 아래에** 둔다(kagglehub 캐시 폴더 구조째 복사하면 경로가 어긋난다). repo에는 올리지 않았고(`.gitignore`, E-02), 아래로 내려받는다.
   `kagglehub.dataset_download("olistbr/brazilian-ecommerce")`
3. 노트북을 번호 순서(01 → 08)로 실행한다. 07은 05가 만든 `data/processed/master_features.parquet`가 있어야 하므로 01~06을 먼저 돌린다.
   DuckDB를 쓰는 노트북은 마지막에 `con.close()`를 실행하고, 다음 노트북을 열기 전에 이전 커널을 종료한다(E-07).
4. 08(`08_wrapup.ipynb`)은 `data/processed/07_outputs/`가 있어야 돌아간다. 이 폴더는 07(`07_baseline.ipynb`) 맨 끝의 7-10 셀을 실행하면 생성되며, `data/processed/`는 `.gitignore` 대상이라 repo에는 없다.
5. 07과 08이 함께 쓰는 정의는 `src/common.py`에 있다. 08 0절은 07이 저장한 예측과 08의 재적합 결과가 일치하는지 assert로 확인한다.
6. 결과 표는 `outputs/tables/`, 그림은 `outputs/figures/`에 저장된다.
7. 정합성 점검: `python tools/check_repo.py` (문서·노트북·표 사이의 파일명, 실행 상태, 숫자 출처를 확인. 진행 중인 노트북은 `--skip-nb 파일명.ipynb`로 임시 제외할 수 있고, 제외한 항목은 실행 결과 맨 위에 표시된다. `tools/key_numbers.json`에 적은 핵심 숫자가 노트북에 있는지도 확인한다).
8. 3단계(리뷰 텍스트 분류, `docs/stage3_step0_rules.md` 참고):
   - `09_stage3_step1_target.ipynb` → `10_stage3_step2_sample.ipynb` 순서로 실행한다. 10은 규칙 문서를 커밋한 뒤 `RULES_COMMITTED=True`와 커밋 해시를 넣고 한 번만 실행한다(라벨링 시작 후에는 다시 실행하지 않는다).
   - 번역(dev만): `pip install google-cloud-translate` 후 Google Cloud 인증(ADC)을 설정하고 `python tools/translate_dev.py`를 실행한다. 결과는 `data/interim/stage3/translations_dev.csv`, 격리 로그는 `docs/stage3_translate_isolation_log.txt`에 저장된다. 인증 파일·원문·번역문은 repo에 올리지 않는다(`.gitignore`).
   - hold-out은 규칙 동결 커밋 전까지 번역·열람하지 않는다.
