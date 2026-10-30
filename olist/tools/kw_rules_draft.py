"""키워드 규칙 개발용 평가 (dev 전용 도구. 동결 대상이 아니며, 동결된 규칙은 tools/kw_rules.py). 처음에는 로컬 전용으로 만들었으나 a6ac430에서 도구로 커밋했다.

규칙 문서 §6-2·§9 기준:
- 텍스트 처리는 dev 204건에서만 한다(hold-out 제외 assert). 이 스크립트는 hold-out 원문을 읽지 않는다.
- 부정어(não, nem, sem, nunca, nada)가 불용어에 없는지 assert로 먼저 확인한다(kw_rules.assert_no_negation_in_stopwords).
- 공식 라벨: dev 1~50은 재라벨(v1), 51~204는 첫 라벨(v1). 51~100 재라벨은 쓰지 않는다.
- 평가 단위는 주 유형(label_main), P9a·P9b는 P9로 합친다. 규칙은 P9를 내지 않고 못 맞추면 '미분류'.
- 출력에는 리뷰 원문을 찍지 않는다(번호와 건수만). 예외: --show A:B는 dev 리뷰 원문을 찍는다(개발용, dev 전용 assert 뒤에만 동작).

사용법 (olist 폴더, (.venv)):
  python tools\\kw_rules_draft.py --text-csv data\\interim\\stage3\\translations_dev.csv --text-col text_pt
  ... --compare                         # 선택 로직 (A)(B) 끈 기준 대 현재 규칙을 유형별로 나란히
  ... --baseline --show P3:P6b --skip 6 --limit 7   # 기준 로직에서 P3인데 P6b로 나온 건 중 앞 6건 건너뛰고 7건의 원문
  ... --misses                          # 틀린 번호만
"""
import argparse
import sys

import pandas as pd

import kw_rules as R

LABELS_CSV = "outputs/labels/stage3_labels_dev.csv"
MANIFEST = "data/processed/stage3/stage3_sample_manifest.csv"
ORDER = R.ORDER


def per_type(df, col):
    out = {}
    for c in ORDER:
        pred = int((df[col] == c).sum())
        tp = int(((df[col] == c) & (df.label_main == c)).sum())
        act = int((df.label_main == c).sum())
        out[c] = (tp, pred, act)
    return out


def fmt(tp, n):
    return f"{tp}/{n}" + (f" = {tp / n:.2f}" if n else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-csv", required=True)
    ap.add_argument("--text-col")
    ap.add_argument("--id-col", default="review_id")
    ap.add_argument("--labels", default=LABELS_CSV)
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--misses", action="store_true", help="틀린 번호만 출력(원문은 안 찍음)")
    ap.add_argument("--baseline", action="store_true", help="선택 로직 (A)(B)를 끈 기준으로 평가·--show")
    ap.add_argument("--compare", action="store_true", help="기준(로직 끔) 대 현재를 유형별로 나란히 출력")
    ap.add_argument("--show", help="예: P3:P6b (공식 라벨 P3인데 규칙이 P6b로 낸 dev 리뷰의 원문을 찍음, 개발용)")
    ap.add_argument("--skip", type=int, default=0, help="--show에서 앞의 N건을 건너뜀(이미 본 건 제외)")
    ap.add_argument("--limit", type=int, default=8, help="--show로 찍을 최대 건수")
    a = ap.parse_args()

    R.assert_no_negation_in_stopwords()
    print("부정어 불용어 assert 통과")

    tx = pd.read_csv(a.text_csv, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not a.text_col or a.text_col not in tx.columns or a.id_col not in tx.columns:
        print("열 이름 목록(내용은 보지 않음):", list(tx.columns))
        print("--text-col에 원문(포르투갈어) 열 이름을 넣어 다시 실행하세요.")
        return 1

    lab = pd.read_csv(a.labels, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    lab["n"] = lab["label_order"].astype(int)
    off = lab[((lab.n <= 50) & (lab["pass"] == "relabel")) | ((lab.n > 50) & (lab["pass"] == "first"))].copy()
    assert (off.codebook_ver == "v1").all(), "공식 라벨에 v1이 아닌 행이 있음"
    assert off.review_id.is_unique, "공식 라벨에 review_id 중복"
    assert len(off) == 204, f"공식 라벨은 204건이어야 함 (현재 {len(off)})"
    off["label_main"] = off["label_main"].replace({"P9a": "P9", "P9b": "P9"})
    off["label_sub"] = off["label_sub"].replace({"P9a": "P9", "P9b": "P9"})

    mf = pd.read_csv(a.manifest, dtype=str, encoding="utf-8-sig")
    dev_ids = set(mf.loc[mf["split"] == "dev", "review_id"])
    assert set(off.review_id) <= dev_ids, "dev가 아닌 review_id가 섞임(hold-out 격리 위반)"
    df = off.merge(tx[[a.id_col, a.text_col]].rename(columns={a.id_col: "review_id", a.text_col: "text"}),
                   on="review_id", how="left")
    assert df.text.notna().all() and len(df) == 204, "원문 병합 후 204건이 아님"
    print("hold-out 격리 assert 통과: 204건 모두 dev")

    df["base"] = df.text.map(lambda t: R.classify(t, partial_override=False, remedy_demote=False))
    df["cur"] = df.text.map(R.classify)
    col = "base" if a.baseline else "cur"
    print(f"\n[개발용] dev 204건: {'기준(선택 로직 (A)(B) 끔)' if a.baseline else '현재 규칙'} 출력 대 공식 라벨 (최종 평가는 hold-out에서만)")
    cats = ORDER + ["P9"]
    cm = pd.crosstab(df.label_main, df[col]).reindex(index=cats, columns=ORDER + ["미분류"], fill_value=0)
    print(cm.to_string())

    print("\n유형별 (개발용): precision = 규칙이 붙인 건 중 라벨 일치, recall = 라벨 건수 중 규칙이 맞춘 건")
    cur = per_type(df, col)
    for c in ORDER:
        tp, pred, act = cur[c]
        print(f"  {c}: precision {fmt(tp, pred)} / recall {fmt(tp, act)}")
    print(f"미분류율: {(df[col] == '미분류').mean():.2f}")

    if a.compare:
        b, n = per_type(df, "base"), per_type(df, "cur")
        print("\n[비교] 기준(로직 끔) → 현재 (precision / recall)")
        for c in ORDER:
            print(f"  {c}: {fmt(b[c][0], b[c][1])} / {fmt(b[c][0], b[c][2])}  →  {fmt(n[c][0], n[c][1])} / {fmt(n[c][0], n[c][2])}")
        print(f"  미분류: {(df.base == '미분류').sum()} → {(df.cur == '미분류').sum()}")
        print(f"  라벨 P3인데 규칙 P6b: {int(((df.label_main == 'P3') & (df.base == 'P6b')).sum())} → {int(((df.label_main == 'P3') & (df.cur == 'P6b')).sum())}")
        print(f"  라벨 P1인데 규칙 P4 : {int(((df.label_main == 'P1') & (df.base == 'P4')).sum())} → {int(((df.label_main == 'P1') & (df.cur == 'P4')).sum())}")
        lost = [c for c in ORDER if n[c][0] < b[c][0]]
        print("  맞춘 건수(TP)가 줄어든 유형:", lost if lost else "없음")

    if a.misses:
        w = df[(df[col] != df.label_main)][["n", "label_main", col]].sort_values("n")
        print("\n틀린 번호:")
        print(w.to_string(index=False))

    if a.show:
        x, y = a.show.split(":")
        sel = df[(df.label_main == x) & (df[col] == y)].sort_values("n")
        w = sel.iloc[a.skip:a.skip + a.limit]
        print(f"\n[dev 원문, 개발용] 공식 라벨 {x} / 규칙 {y}: {len(sel)}건 중 {a.skip + 1}번째부터 {len(w)}건")
        for _, r in w.iterrows():
            print(f"#{r['n']}: {r['text']}")

    print(f"\nkw_rules.py 전체 sha256(앞 12자, 동결 때 log에 적음): {R.file_sha256()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
