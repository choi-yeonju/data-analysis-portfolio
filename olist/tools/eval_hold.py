"""3단계 hold-out 키워드 규칙 평가 (규칙 문서 §6). 동결 커밋 뒤, hold-out 라벨링이 106건 모두 끝난 뒤에 한 번만 실행한다.

  python tools\\eval_hold.py --freeze-commit <해시> --rules-sha <12자>

평가: 유형별 precision·recall(Wilson 95% 구간, 건수 병기), confusion matrix(행=사람 라벨, 열=규칙 출력, '미분류' 열 포함), 미분류율.
표기(§6): 평가 건수 < 15 → "소표본"(precision은 규칙이 붙인 건수, recall은 사람 라벨 건수를 각각 15와 비교, 해당 지표에만),
          precision < 70% → "추정치". 주 유형 기준, P9a·P9b는 P9로 합침. 규칙은 P9를 내지 않는다.
격리 증빙(§2): 이 스크립트가 라벨·원문의 review_id가 모두 hold-out이고 dev가 아님을 assert하고 그 출력을 보여 준다.
결과 표는 건수와 비율만 저장한다(원문 없음). 이미 결과 파일이 있으면 --again 없이는 다시 돌리지 않는다(결과를 보고 고치지 않기 위해).
이 스크립트는 규칙을 고치지 않는다. 가중 비중·H1~H3·교차분석은 별도 스크립트에서 한다.
"""
import argparse
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hold_guard  # noqa: E402

LABELS = Path("outputs/labels/stage3_labels_hold.csv")
TRANS = Path("data/interim/stage3/translations_hold.csv")
MANIFEST = Path("data/processed/stage3/stage3_sample_manifest.csv")
OUT_DIR = Path("outputs/tables")
OUT = OUT_DIR / "stage3_holdout_rule_eval.csv"
OUT_CM = OUT_DIR / "stage3_holdout_rule_confusion.csv"
N_HOLD = 106
TYPES = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b"]


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-commit", required=True)
    ap.add_argument("--rules-sha", required=True)
    ap.add_argument("--labels", default=str(LABELS))
    ap.add_argument("--text-csv", default=str(TRANS))
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--again", action="store_true", help="결과 파일이 있어도 다시 계산(이유를 log에 적을 것)")
    a = ap.parse_args()

    _, _, guard_msg = hold_guard.assert_frozen(a.freeze_commit, a.rules_sha)
    if OUT.exists() and not a.again:
        print(f"중단: {OUT} 이(가) 이미 있음. 평가는 한 번만 한다(--again 으로 다시 돌리면 이유를 log에 적을 것)")
        return 1
    import kw_rules

    lab = pd.read_csv(a.labels, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert (lab["pass"] == "first").all() and lab["review_id"].is_unique, "hold-out 라벨은 첫 라벨만, review_id 유일해야 함"
    assert len(lab) == N_HOLD, f"hold-out 라벨이 {N_HOLD}건이 아님({len(lab)}). 라벨링을 모두 끝낸 뒤에 평가"
    assert (lab["label_main"] != "").all() and (lab["codebook_ver"] == "v1").all(), "빈 라벨이 있거나 코드북이 v1이 아님"
    lab["label_main"] = lab["label_main"].replace({"P9a": "P9", "P9b": "P9"})
    man = pd.read_csv(a.manifest, dtype=str)
    hold_ids = set(man.loc[man["split"] == "hold", "review_id"])
    dev_ids = set(man.loc[man["split"] == "dev", "review_id"])
    tx = pd.read_csv(a.text_csv, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert set(lab["review_id"]) == hold_ids and not (set(lab["review_id"]) & dev_ids), "라벨이 hold-out 106건과 다름"
    assert set(tx["review_id"]) == hold_ids, "원문 파일이 hold-out 106건과 다름"
    print("hold-out 격리 증빙: 라벨 106건·원문 106건 모두 hold-out, dev 교집합 0건")
    kw_rules.assert_no_negation_in_stopwords()
    print("부정어 불용어 assert 통과")

    df = lab.merge(tx[["review_id", "text_pt"]], on="review_id", validate="1:1")
    df["rule"] = df["text_pt"].map(kw_rules.classify)

    rows = []
    for c in TYPES:
        n_pred = int((df.rule == c).sum())
        tp = int(((df.rule == c) & (df.label_main == c)).sum())
        n_lab = int((df.label_main == c).sum())
        p = tp / n_pred if n_pred else float("nan")
        r = tp / n_lab if n_lab else float("nan")
        plo, phi = wilson(tp, n_pred)
        rlo, rhi = wilson(tp, n_lab)
        rows.append({
            "type": c, "n_pred": n_pred, "tp": tp, "precision": p, "p_lo": plo, "p_hi": phi,
            "p_flag": ", ".join(f for f, on in (("소표본", n_pred < 15), ("추정치", n_pred > 0 and p < 0.70)) if on),
            "n_label": n_lab, "recall": r, "r_lo": rlo, "r_hi": rhi, "r_flag": "소표본" if n_lab < 15 else "",
        })
    res = pd.DataFrame(rows)
    cm = pd.crosstab(df.label_main, df.rule).reindex(index=TYPES + ["P9"], columns=TYPES + ["미분류"], fill_value=0)

    print("\n[hold-out] 규칙 출력 대 사람 라벨 (행=사람, 열=규칙)")
    print(cm.to_string())
    print("\n유형별: precision = 규칙이 붙인 건 중 일치, recall = 사람 라벨 건수 중 규칙이 맞춘 건 (Wilson 95%)")
    for r in rows:
        def f(k, n, lo, hi):
            return f"{k}/{n}" + (f" = {k / n:.2f} [{lo:.2f}, {hi:.2f}]" if n else " = 계산 불가")
        print(f"  {r['type']}: precision {f(r['tp'], r['n_pred'], r['p_lo'], r['p_hi'])}"
              f"{'  <' + r['p_flag'] + '>' if r['p_flag'] else ''}"
              f" / recall {f(r['tp'], r['n_label'], r['r_lo'], r['r_hi'])}{'  <' + r['r_flag'] + '>' if r['r_flag'] else ''}")
    unc = float((df.rule == "미분류").mean())
    print(f"미분류율: {unc:.2f} ({int((df.rule == '미분류').sum())}/{N_HOLD})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False, encoding="utf-8-sig")
    cm.to_csv(OUT_CM, encoding="utf-8-sig")
    print(f"\n저장: {OUT}, {OUT_CM} (건수·비율만, 원문 없음)")
    print(f"kw_rules.py sha256 {kw_rules.file_sha256()} (동결 때 기록한 값과 같아야 함)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
