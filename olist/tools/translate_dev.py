"""3단계 dev 리뷰 번역 (Google Cloud Translation Basic v2, 포르투갈어 -> 한국어).

규칙(stage3_step0_rules_v12 §2) 준수:
- hold-out review_id는 원문을 메모리에 올리기 전에 제외한다 (CSV를 chunk로 읽으며 dev id만 남김).
- hold-out 격리 assert 출력을 docs/stage3_translate_isolation_log.txt 로 저장 (결과 문서 첨부용).
- 번역 결과는 별도 캐시 파일에만 쓴다. 라벨링 작업 파일은 건드리지 않는다.

실행 (프로젝트 루트에서):
    python translate_dev.py --dry-run          # API 호출 없이 건수·글자 수만 확인
    python translate_dev.py --limit 5          # 5건만 시험 번역
    python translate_dev.py                    # dev 전체 (이미 번역된 건은 건너뜀)
"""
import argparse
import hashlib
import time
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

import pandas as pd

MANIFEST = Path("data/processed/stage3/stage3_sample_manifest.csv")
MANIFEST_SHA256 = "c4469f548bf6f2c7402192cc6d54c563a54271e0405a2dfc7f57e158c8a606fb"
RAW_REVIEWS = Path("data/raw/olist_order_reviews_dataset.csv")
OUT = Path("data/interim/stage3/translations_dev.csv")
LOG = Path("docs/stage3_translate_isolation_log.txt")

EXPECTED_DEV, EXPECTED_HOLDOUT = 204, 106  # 규칙 문서 §2 (합계 310)
BATCH = 50          # v2는 요청당 최대 128개. 여유 있게 50
SRC_LANG = "pt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_dev_texts(dev_ids: set, hold_ids: set) -> pd.DataFrame:
    """원문을 chunk로 읽으며 dev id만 남긴다. hold-out 원문은 DataFrame에 올라오지 않는다."""
    parts = []
    for chunk in pd.read_csv(
        RAW_REVIEWS,
        usecols=["review_id", "review_comment_message"],
        chunksize=20000,
    ):
        parts.append(chunk[chunk["review_id"].isin(dev_ids)])
    df = pd.concat(parts, ignore_index=True)
    # 같은 review_id가 여러 주문에 붙어 있어도 본문은 동일 (규칙 문서 §1)
    df = df.drop_duplicates("review_id").rename(columns={"review_comment_message": "text_pt"})
    assert not (set(df["review_id"]) & hold_ids), "hold-out review_id가 섞여 들어옴"
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="ko", help="번역 대상 언어 (기본 ko, 영어는 en)")
    ap.add_argument("--dev-value", default="dev", help="manifest split 열의 dev 값")
    ap.add_argument("--holdout-value", default="hold", help="manifest split 열의 hold-out 값")
    ap.add_argument("--limit", type=int, default=None, help="label_order 앞에서부터 N건만")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 건수·글자 수만 출력")
    ap.add_argument("--skip-sha", action="store_true", help="manifest sha256 확인 생략")
    args = ap.parse_args()

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    # 1) manifest 확인
    if not args.skip_sha:
        got = sha256(MANIFEST)
        assert got == MANIFEST_SHA256, f"manifest sha256 불일치: {got}"
        log(f"[ok] manifest sha256 일치 ({got[:8]}…{got[-6:]})")

    man = pd.read_csv(MANIFEST)
    log(f"manifest split 값: {man['split'].value_counts().to_dict()}")
    assert man["review_id"].is_unique, "manifest review_id 중복"
    assert set(man["split"]) == {args.dev_value, args.holdout_value}, (
        f"split 값이 예상과 다름: {set(man['split'])} → --dev-value / --holdout-value 로 지정")

    dev = man[man["split"] == args.dev_value]
    hold = man[man["split"] == args.holdout_value]
    assert len(dev) == EXPECTED_DEV and len(hold) == EXPECTED_HOLDOUT, (
        f"건수 불일치 dev={len(dev)} hold-out={len(hold)}")
    dev_ids, hold_ids = set(dev["review_id"]), set(hold["review_id"])
    assert not (dev_ids & hold_ids)
    log(f"[ok] dev {len(dev_ids)} / hold-out {len(hold_ids)} (hold-out은 원문 로딩 전에 제외)")

    # 2) dev 원문만 로드
    texts = load_dev_texts(dev_ids, hold_ids)
    assert len(texts) == EXPECTED_DEV, f"dev 원문 {len(texts)}건 (기대 {EXPECTED_DEV})"
    assert texts["text_pt"].notna().all() and (texts["text_pt"].str.strip() != "").all(), "빈 원문 존재"
    log(f"[ok] 로드된 원문 {len(texts)}건 모두 dev, hold-out 교집합 {len(set(texts['review_id']) & hold_ids)}건")

    df = texts.merge(dev[["review_id", "label_order"]], on="review_id", validate="1:1")
    df = df.sort_values("label_order").reset_index(drop=True)
    if args.limit:
        df = df.head(args.limit)

    # 3) 이미 번역된 건 건너뜀 (재개 가능)
    done = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=["review_id"])
    todo = df[~df["review_id"].isin(set(done["review_id"]))]
    n_chars = int(todo["text_pt"].str.len().sum())
    log(f"번역 대상 {len(todo)}건 / {n_chars}자 (이미 완료 {len(done)}건)")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    if args.dry_run or todo.empty:
        return

    # 4) 번역 (ADC 인증: gcloud auth application-default login)
    from google.cloud import translate_v2 as translate
    client = translate.Client()
    try:
        lib_ver = version("google-cloud-translate")
    except PackageNotFoundError:
        lib_ver = "unknown"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(todo), BATCH):
        batch = todo.iloc[start:start + BATCH]
        for attempt in range(4):
            try:
                res = client.translate(
                    list(batch["text_pt"]),
                    target_language=args.target,
                    source_language=SRC_LANG,
                    format_="text",   # HTML 이스케이프 방지
                )
                break
            except Exception as e:  # 일시 오류만 재시도
                if attempt == 3:
                    raise
                wait = 2 ** attempt
                print(f"재시도 {attempt + 1} ({e}); {wait}초 대기")
                time.sleep(wait)

        out = pd.DataFrame({
            "review_id": batch["review_id"].values,
            "label_order": batch["label_order"].values,
            "text_pt": batch["text_pt"].values,
            "text_tr": [r["translatedText"] for r in res],
            "tool": "google-cloud-translation-v2-basic",
            "lib_version": lib_ver,
            "target_lang": args.target,
            "translated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        out.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, encoding="utf-8-sig")
        print(f"{min(start + BATCH, len(todo))}/{len(todo)} 저장")

    # 5) 사후 검증: 결과 파일에 hold-out이 없어야 함
    final = pd.read_csv(OUT)
    assert not (set(final["review_id"]) & hold_ids), "번역 결과에 hold-out 포함"
    assert final["review_id"].is_unique
    msg = f"[ok] 번역 결과 {len(final)}건, hold-out 교집합 0건, tool={final['tool'].iloc[0]}, lib={lib_ver}"
    print(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


if __name__ == "__main__":
    main()
