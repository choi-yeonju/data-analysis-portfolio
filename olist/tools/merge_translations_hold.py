"""hold-out 번역 캐시(text_tr)로 라벨링 작업 파일(stage3_label_hold.csv)을 만든다. merge_translations_dev.py의 hold-out 판.

실행 (olist 폴더, .venv):
  python tools/merge_translations_hold.py --freeze-commit <동결 커밋 해시> --rules-sha <12자>

- 동결 확인(hold_guard)을 통과해야만 실행된다. 원문·번역은 화면에 출력하지 않는다(건수만).
- 입력: data/interim/stage3/translations_hold.csv (translate_hold.py 결과), manifest(label_order만 사용)
- 출력: data/processed/stage3/stage3_label_hold.csv (열: review_id, label_order, text_pt, text_ko, 라벨 5열은 빈칸)
- 이미 출력 파일이 있으면 덮어쓰지 않고 중단한다(라벨이 들어 있을 수 있음).
- manifest의 hold 행에 label_order가 없거나 비어 있으면 review_id의 sha256 순서로 1..106을 매긴다(층 정보가 새지 않는 고정 순서).
"""
import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hold_guard  # noqa: E402

CACHE = Path("data/interim/stage3/translations_hold.csv")
MANIFEST = Path("data/processed/stage3/stage3_sample_manifest.csv")
OUT = Path("data/processed/stage3/stage3_label_hold.csv")
LABEL_COLS = ["label_main", "label_sub", "mentions_freight_cost", "codebook_ver", "memo"]


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def stop(msg):
    print("중단:", msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-commit", required=True)
    ap.add_argument("--rules-sha", required=True)
    a = ap.parse_args()
    hold_guard.assert_frozen(a.freeze_commit, a.rules_sha)

    if OUT.exists():
        stop(f"{OUT} 이(가) 이미 있음. 덮어쓰지 않음(라벨이 들어 있을 수 있음)")
    cache, man = rd(CACHE), rd(MANIFEST)
    for need in ("review_id", "text_pt", "text_tr"):
        if need not in cache.columns:
            stop(f"{CACHE}에 '{need}' 열이 없음. 현재 열: {list(cache.columns)}")
    hold = man[man["split"] == "hold"]
    if len(hold) != 106 or len(cache) != 106:
        stop(f"hold-out 106건이 아님(manifest {len(hold)}, 번역 {len(cache)})")
    if cache["review_id"].duplicated().any() or set(cache["review_id"]) != set(hold["review_id"]):
        stop("번역 캐시의 review_id가 manifest hold-out과 다르거나 중복")
    if (cache["text_tr"].str.strip() == "").any() or (cache["text_pt"].str.strip() == "").any():
        stop("원문 또는 번역이 빈 행이 있음")

    d = cache[["review_id", "text_pt", "text_tr"]].rename(columns={"text_tr": "text_ko"})
    lo = hold[["review_id"]].assign(label_order=hold["label_order"] if "label_order" in hold.columns else "")
    d = d.merge(lo, on="review_id", validate="1:1")
    if (d["label_order"].str.strip() == "").any():
        d = d.assign(_h=d["review_id"].map(lambda s: hashlib.sha256(s.encode()).hexdigest())).sort_values("_h")
        d["label_order"] = [str(i) for i in range(1, len(d) + 1)]
        d = d.drop(columns="_h")
        print("label_order: manifest에 없어 review_id 해시 순서로 1~106을 매김")
    else:
        print("label_order: manifest 값 사용")
    if d["label_order"].duplicated().any():
        stop("label_order 중복")
    for c in LABEL_COLS:
        d[c] = ""
    d = d.assign(_o=d["label_order"].astype(int)).sort_values("_o").drop(columns="_o")
    d = d[["review_id", "label_order", "text_pt", "text_ko"] + LABEL_COLS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"완료: {OUT} {len(d)}행 (text_ko 채움, 라벨 칸 비어 있음)")


if __name__ == "__main__":
    main()
