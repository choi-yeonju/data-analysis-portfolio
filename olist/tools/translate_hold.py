"""3단계 hold-out 리뷰 번역 (Google Cloud Translation Basic v2, 포르투갈어 -> 한국어). translate_dev.py의 hold-out 판.

규칙(docs/stage3_step0_rules.md §2·§6-2) 준수:
- 규칙 동결 커밋이 있고 tools/kw_rules.py 가 그 커밋과 같을 때만 실행한다(hold_guard). 동결 전에는 실행하지 않는다.
- 원본 CSV를 chunk로 읽으며 hold-out id만 남긴다. dev 행은 결과에 남기지 않는다.
- 번역 결과는 별도 캐시 파일에만 쓴다(.gitignore 대상). 원문·번역은 로그나 터미널에 찍지 않는다.
- 격리 assert 출력을 docs/stage3_translate_hold_log.txt 로 저장한다(건수·해시만, 원문 없음).

실행 (olist 폴더, (.venv)):
    python tools/translate_hold.py --freeze-commit <동결 커밋 해시> --rules-sha <kw_rules.py 해시 12자> --dry-run
    python tools/translate_hold.py --freeze-commit ... --rules-sha ...            # 이미 번역된 건은 건너뜀
"""
import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hold_guard  # noqa: E402

MANIFEST = Path("data/processed/stage3/stage3_sample_manifest.csv")
MANIFEST_SHA256 = "c4469f548bf6f2c7402192cc6d54c563a54271e0405a2dfc7f57e158c8a606fb"
RAW_REVIEWS = Path("data/raw/olist_order_reviews_dataset.csv")
OUT = Path("data/interim/stage3/translations_hold.csv")
LOG = Path("docs/stage3_translate_hold_log.txt")

EXPECTED_DEV, EXPECTED_HOLDOUT = 204, 106  # 규칙 문서 §2 (합계 310)
BATCH = 50
SRC_LANG = "pt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_hold_texts(hold_ids: set, dev_ids: set) -> pd.DataFrame:
    parts = []
    for chunk in pd.read_csv(RAW_REVIEWS, usecols=["review_id", "review_comment_message"],
                             chunksize=20000, dtype=str, keep_default_na=False):
        parts.append(chunk[chunk["review_id"].isin(hold_ids)])
    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates("review_id").rename(columns={"review_comment_message": "text_pt"})
    assert not (set(df["review_id"]) & dev_ids), "dev review_id가 섞여 들어옴"
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-commit", required=True, help="규칙 동결 커밋 해시")
    ap.add_argument("--rules-sha", required=True, help="동결한 tools/kw_rules.py 의 file_sha256 (12자)")
    ap.add_argument("--target", default="ko")
    ap.add_argument("--dev-value", default="dev")
    ap.add_argument("--holdout-value", default="hold")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 건수·글자 수만 출력")
    ap.add_argument("--skip-sha", action="store_true")
    args = ap.parse_args()

    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    _, _, guard_msg = hold_guard.assert_frozen(args.freeze_commit, args.rules_sha, echo=False)
    log(guard_msg)

    if not args.skip_sha:
        got = sha256(MANIFEST)
        assert got == MANIFEST_SHA256, f"manifest sha256 불일치: {got}"
        log(f"[ok] manifest sha256 일치 ({got[:8]}…{got[-6:]})")

    man = pd.read_csv(MANIFEST, dtype=str)
    log(f"manifest split 값: {man['split'].value_counts().to_dict()}")
    assert man["review_id"].is_unique, "manifest review_id 중복"
    assert set(man["split"]) == {args.dev_value, args.holdout_value}, f"split 값이 예상과 다름: {set(man['split'])}"
    dev = man[man["split"] == args.dev_value]
    hold = man[man["split"] == args.holdout_value].copy()
    assert len(dev) == EXPECTED_DEV and len(hold) == EXPECTED_HOLDOUT, f"건수 불일치 dev={len(dev)} hold-out={len(hold)}"
    dev_ids, hold_ids = set(dev["review_id"]), set(hold["review_id"])
    assert not (dev_ids & hold_ids)
    log(f"[ok] dev {len(dev_ids)} / hold-out {len(hold_ids)} (이 스크립트는 hold-out만 번역, dev는 결과에 남기지 않음)")

    texts = load_hold_texts(hold_ids, dev_ids)
    assert len(texts) == EXPECTED_HOLDOUT, f"hold-out 원문 {len(texts)}건 (기대 {EXPECTED_HOLDOUT})"
    assert texts["text_pt"].notna().all() and (texts["text_pt"].str.strip() != "").all(), "빈 원문 존재"
    log(f"[ok] 로드된 원문 {len(texts)}건 모두 hold-out, dev 교집합 {len(set(texts['review_id']) & dev_ids)}건")

    if "label_order" in hold.columns:
        order = hold[["review_id", "label_order"]]
    else:
        order = hold[["review_id"]].assign(label_order="")
    df = texts.merge(order, on="review_id", validate="1:1")
    df = df.sort_values("review_id").reset_index(drop=True)      # 층 정보가 번역 순서에 새지 않게 review_id 순
    if args.limit:
        df = df.head(args.limit)

    done = pd.read_csv(OUT, dtype=str) if OUT.exists() else pd.DataFrame(columns=["review_id"])
    todo = df[~df["review_id"].isin(set(done["review_id"]))]
    n_chars = int(todo["text_pt"].str.len().sum())
    log(f"번역 대상 {len(todo)}건 / {n_chars}자 (이미 완료 {len(done)}건)")

    if args.dry_run or todo.empty:
        return

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

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
                res = client.translate(list(batch["text_pt"]), target_language=args.target,
                                       source_language=SRC_LANG, format_="text")
                break
            except Exception as e:
                if attempt == 3:
                    raise
                wait = 2 ** attempt
                print(f"재시도 {attempt + 1} ({type(e).__name__}); {wait}초 대기")
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

    final = pd.read_csv(OUT, dtype=str)
    assert not (set(final["review_id"]) & dev_ids), "번역 결과에 dev 포함"
    assert final["review_id"].is_unique
    msg = f"[ok] 번역 결과 {len(final)}건, dev 교집합 0건, tool={final['tool'].iloc[0]}, lib={lib_ver}"
    print(msg)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


if __name__ == "__main__":
    main()
