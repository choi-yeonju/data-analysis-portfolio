## 재현 방법

환경: Python 3.13.9, `olist/.venv` (E-05). VS Code에서 `olist` 폴더를 열어 작업한다(노트북 경로 기준이 프로젝트 루트, E-04).

1. 패키지 설치: `pip install -r requirements.txt`
2. 원본 데이터: `data/raw/`에 Olist CSV 9개를 **하위 폴더 없이 바로 아래에** 둔다(`data/raw/`·`interim/`·`processed/`는 저장소에 빈 폴더로 들어 있다)(kagglehub 캐시 폴더 구조째 복사하면 경로가 어긋난다). repo에는 올리지 않았고(`.gitignore`, E-02), 아래로 내려받는다.
   `kagglehub.dataset_download("olistbr/brazilian-ecommerce")`
3. 노트북을 번호 순서(01 → 08)로 실행한다. 작업 폴더가 `olist`여야 하므로 Jupyter Lab·Notebook에서는 각 노트북 맨 위에서 `%cd ..`를 먼저 실행한다(VS Code는 설정으로 자동). 07은 05가 만든 `data/processed/master_features.parquet`가 있어야 하므로 01\~06을 먼저 돌린다.
   DuckDB를 쓰는 노트북은 마지막에 `con.close()`를 실행하고, 다음 노트북을 열기 전에 이전 커널을 종료한다(E-07).
4. 08(`08_wrapup.ipynb`)은 `data/processed/07_outputs/`가 있어야 돌아간다. 이 폴더는 07(`07_baseline.ipynb`) 맨 끝의 7-10 셀을 실행하면 생성되며, `data/processed/`는 `.gitignore` 대상이라 repo에는 없다.
5. 07과 08이 함께 쓰는 정의는 `src/common.py`에 있다. 08 0절은 07이 저장한 예측과 08의 재적합 결과가 일치하는지 assert로 확인한다.
6. 결과 표는 `outputs/tables/`, 그림은 `outputs/figures/`에 저장된다.
7. 정합성 점검: `python tools/check_repo.py` (문서·노트북·표 사이의 파일명, 실행 상태, 숫자 출처를 확인. 진행 중인 노트북은 `--skip-nb 파일명.ipynb`로 임시 제외할 수 있고, 제외한 항목은 실행 결과 맨 위에 표시된다. `tools/key_numbers.json`에 적은 핵심 숫자가 노트북에 있는지도 확인한다).
8. 3단계(리뷰 텍스트 분류, `docs/stage3_step0_rules.md`, 결정 기록은 `docs/decisions.md` D-27\~D-34). 모든 명령은 `olist` 폴더, `(.venv)`에서 실행한다. hold-out을 여는 명령은 동결 커밋과 규칙 해시(`--freeze-commit 252854b4ef6746a693f601d865ccde5097366b8c --rules-sha 7e3c0952f98c`)를 확인한다.
   1. 대상 숫자 재현: `python tools\repro_stage3_sec1.py`(8,247 / 6,449 / 6,400).
   2. 표본: `09_stage3_step1_target.ipynb` → `10_stage3_step2_sample.ipynb`(규칙 문서를 커밋한 뒤 `RULES_COMMITTED=True`와 커밋 해시를 넣고 한 번만 실행, 라벨링 시작 후에는 다시 실행하지 않는다).
   3. dev 번역·병합·라벨링: `translate_dev.py` → `merge_translations_dev.py` → `label_dev.py`(`--pass`, `--ver v1` 옵션은 `--help`로 확인). 재라벨 후 `compute_kappa.py`(kappa 0.864, 통과, D-32).
   4. 키워드 규칙: 개발 중에는 `kw_rules_draft.py --compare`(dev 전용), 동결은 `tools\kw_rules.py` 하나만 커밋(D-33).
   5. hold-out(동결 이후, 각 단계가 `hold_guard`로 동결을 확인): `translate_hold.py` → `merge_translations_hold.py` → `label_hold.py`(규칙 출력을 보지 않고 라벨링, 끝난 뒤 `--export`로 원문·번역·메모 없는 라벨 파일 생성) → `eval_hold.py`(1회, 결과 파일이 있으면 거부).
   6. 집계: `python tools\stage3_results.py --freeze-commit ... --rules-sha ...`가 공식 집계다. `python tools\report_stage3.py`는 교차검증용이다(D-34). 8월 제외 민감도는 `data/processed/stage3_target_6400.parquet`가 있어야 계산된다(D-35).
   7. 결과 정리: `notebooks/11_stage3_results.ipynb`(Restart & Run All). 6의 결과 표와 커밋된 라벨 파일만 읽어 표·그림을 만들고(`outputs/figures/11_*.png`), 숫자가 결과 문서와 같은지 assert로 확인한다. 결과 해설은 `docs/stage3_results.md`.
   8. 원문·번역문이 든 `data/` 파일은 올리지 않는다. 번역은 dev와 hold-out 모두 Google Cloud 인증(ADC)이 필요하고 인증 파일은 올리지 않는다. 샘플 manifest의 sha256은 Windows에서 만든 파일 기준이라 다른 OS에서 다시 만들면 값이 다를 수 있다.
