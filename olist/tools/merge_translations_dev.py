"""dev 번역 캐시(text_tr)를 dev 라벨링 작업 파일의 text_ko 열로 합친다.

실행 (olist 폴더, .venv):  python tools\\merge_translations_dev.py [번역캐시경로]
- dev 파일만 읽고 쓴다. hold-out 파일은 열지 않는다.
- 리뷰 원문·번역은 화면에 출력하지 않는다(건수만).
- 라벨·메모 열에 입력된 값이 하나라도 있으면 중단한다. 이미 합쳐져 있으면(같은 값) 변경 없이 끝낸다.
- 합치기 전에 라벨 파일을 같은 폴더에 백업한다(stage3_label_dev.before_merge.csv, 커밋 대상 아님).
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/interim/stage3/translations_dev.csv")
LABEL = Path("data/processed/stage3/stage3_label_dev.csv")
BACKUP = LABEL.with_name("stage3_label_dev.before_merge.csv")
PROTECT = ["label_main", "label_sub", "mentions_freight_cost", "codebook_ver", "memo"]


def norm(s):
    return " ".join(str(s).split())      # 줄바꿈·연속 공백 차이는 같은 글로 본다


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def stop(msg):
    print("중단:", msg)
    sys.exit(1)


cache, lab = rd(CACHE), rd(LABEL)
for need in ("review_id", "text_pt", "text_tr"):
    if need not in cache.columns:
        stop(f"{CACHE}에 '{need}' 열이 없음. 현재 열: {list(cache.columns)}")
for need in ["review_id", "text_pt", "text_ko"] + PROTECT:
    if need not in lab.columns:
        stop(f"{LABEL}에 '{need}' 열이 없음. 현재 열: {list(lab.columns)}")

print("라벨 파일 행:", len(lab), "/ 번역 캐시 행:", len(cache))
if len(lab) != 204:
    stop(f"dev 라벨 파일이 204행이 아님({len(lab)})")
if lab["review_id"].duplicated().any() or cache["review_id"].duplicated().any():
    stop("review_id 중복")
if set(lab["review_id"]) != set(cache["review_id"]):
    only_l = len(set(lab["review_id"]) - set(cache["review_id"]))
    only_c = len(set(cache["review_id"]) - set(lab["review_id"]))
    stop(f"review_id 집합이 다름: 라벨에만 {only_l}, 캐시에만 {only_c}")

filled = int(lab[PROTECT].apply(lambda s: s.str.strip() != "").any(axis=1).sum())
if filled:
    stop(f"라벨·메모가 입력된 행 {filled}건. 병합 중단")

m = lab.merge(cache[["review_id", "text_pt", "text_tr"]], on="review_id", how="left", suffixes=("", "_cache"))
assert len(m) == 204
exact = int((m["text_pt"] == m["text_pt_cache"]).sum())
loose = int((m["text_pt"].map(norm) == m["text_pt_cache"].map(norm)).sum())
print(f"원문 일치: 완전 일치 {exact} / 줄바꿈·공백 무시 일치 {loose} / 204")
if loose != 204:
    stop(f"원문이 다른 행 {204 - loose}건. 번역과 라벨 파일의 짝이 어긋났을 수 있음")
if (m["text_tr"].str.strip() == "").any():
    stop(f"번역이 빈 행 {(m['text_tr'].str.strip() == '').sum()}건")

already = (lab["text_ko"].str.strip() != "")
if already.any():
    if (m.loc[already.values, "text_tr"].values == lab.loc[already, "text_ko"].values).all() and already.sum() == 204:
        print("이미 합쳐져 있음. 변경 없음")
        sys.exit(0)
    stop(f"text_ko가 이미 {int(already.sum())}건 채워져 있고 캐시와 다름. 덮어쓰지 않음")

shutil.copyfile(LABEL, BACKUP)
lab["text_ko"] = m["text_tr"].values
lab.to_csv(LABEL, index=False, encoding="utf-8-sig")
chk = rd(LABEL)
assert len(chk) == 204 and (chk["text_ko"].str.strip() != "").all()
assert list(chk["review_id"]) == list(rd(BACKUP)["review_id"])
print("병합 완료: text_ko 204/204 채움 (백업:", BACKUP.name + ")")
