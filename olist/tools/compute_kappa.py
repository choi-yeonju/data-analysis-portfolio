"""dev 51~100 자기 일관성 kappa 계산 (D-31).

입력: `--export`로 만든 outputs/labels/stage3_labels_dev.csv
      (열: review_id, label_order, pass, label_main, label_sub, mentions_freight_cost, codebook_ver)
쌍:   같은 review_id의 첫 라벨(pass=first, v1)과 재라벨(pass=relabel, v1), label_order 51~100
기준: label_main(주 유형), P9a·P9b는 P9로 합침. 가중치 없는 Cohen's kappa.
통과: 점추정 >= 0.6 (규칙 문서 §5). 일치율은 병기만 하고 판정에는 쓰지 않는다.
구간: 쌍 단위 부트스트랩 2,000회, 시드 고정, 2.5·97.5 백분위. kappa가 정의되지 않는
      재표본(두 라벨이 모두 한 유형뿐이라 기대 일치가 1)은 제외하고 그 횟수를 출력한다.

재라벨을 끝내기 전에는 실행하지 않는다(51~100 첫 라벨을 열어 보지 않기 위해).
리뷰 원문은 읽지 않는다(입력 파일에 없음).
"""
import argparse
import sys

import numpy as np
import pandas as pd

SEED = 20261026
N_BOOT = 2000
THRESHOLD = 0.6
ORDER = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b", "P9"]


def merge_p9(s: pd.Series) -> pd.Series:
    return s.replace({"P9a": "P9", "P9b": "P9"})


def kappa(a: np.ndarray, b: np.ndarray) -> float:
    """가중치 없는 Cohen's kappa. 기대 일치가 1이면 NaN."""
    n = len(a)
    cats = np.union1d(a, b)
    po = float(np.mean(a == b))
    pe = 0.0
    for c in cats:
        pe += (np.sum(a == c) / n) * (np.sum(b == c) / n)
    if np.isclose(pe, 1.0):
        return float("nan")
    return (po - pe) / (1.0 - pe)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="outputs/labels/stage3_labels_dev.csv")
    ap.add_argument("--lo", type=int, default=51)
    ap.add_argument("--hi", type=int, default=100)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df["n"] = df["label_order"].astype(int)
    df = df[(df["n"] >= args.lo) & (df["n"] <= args.hi) & (df["codebook_ver"] == "v1")]
    first = df[df["pass"] == "first"].set_index("review_id")
    relab = df[df["pass"] == "relabel"].set_index("review_id")
    expected = args.hi - args.lo + 1
    if len(first) != expected or len(relab) != expected:
        print(f"중단: 첫 라벨 {len(first)}건, 재라벨 {len(relab)}건 (각 {expected}건이어야 함). "
              "재라벨이 끝났고 --export를 다시 실행했는지 확인하세요.")
        return 1
    if set(first.index) != set(relab.index):
        print("중단: 첫 라벨과 재라벨의 review_id 집합이 다릅니다.")
        return 1
    ids = sorted(first.index, key=lambda i: int(first.loc[i, "label_order"]))
    a = merge_p9(first.loc[ids, "label_main"]).to_numpy()
    b = merge_p9(relab.loc[ids, "label_main"]).to_numpy()
    nums = first.loc[ids, "label_order"].astype(int).to_numpy()
    if (a == "").any() or (b == "").any():
        print("중단: 빈 label_main이 있습니다.")
        return 1

    k = kappa(a, b)
    agree = float(np.mean(a == b))

    rng = np.random.default_rng(args.seed)
    n = len(a)
    ks, skipped = [], 0
    for _ in range(args.n_boot):
        idx = rng.integers(0, n, n)
        kb = kappa(a[idx], b[idx])
        if np.isnan(kb):
            skipped += 1
        else:
            ks.append(kb)
    lo, hi = (np.percentile(ks, [2.5, 97.5]) if ks else (float("nan"), float("nan")))

    print(f"dev {args.lo}~{args.hi} 자기 일관성 (주 유형, P9a·P9b는 P9로 합침), 쌍 {n}개")
    print(f"일치율: {agree:.3f} ({int(np.sum(a == b))}/{n})  [참고, 판정에는 쓰지 않음]")
    print(f"kappa 점추정: {k:.3f}")
    print(f"부트스트랩 95% 구간: [{lo:.3f}, {hi:.3f}] "
          f"(재표본 {args.n_boot}회, 시드 {args.seed}, kappa 정의 불가로 제외 {skipped}회)")
    if np.isnan(k):
        verdict = "계산 불가(두 라벨이 모두 한 유형뿐이라 kappa가 정의되지 않음)"
    else:
        verdict = "통과" if k >= THRESHOLD else "미달"
    note = ""
    if lo < THRESHOLD <= k or (k < THRESHOLD <= hi):
        note = " (구간이 기준 0.6에 걸침: 구간 넓음. 코드북 실패를 뜻하지는 않음)"
    print(f"판정(점추정 >= {THRESHOLD}): {verdict}{note}")

    print("\n유형별 분포")
    dist = pd.DataFrame({
        "첫 라벨": pd.Series(a).value_counts(),
        "재라벨": pd.Series(b).value_counts(),
    }).reindex(ORDER).fillna(0).astype(int)
    print(dist.to_string())

    print("\n혼동 행렬 (행=첫 라벨, 열=재라벨)")
    cm = pd.crosstab(pd.Series(a, name="첫 라벨"), pd.Series(b, name="재라벨"))
    cm = cm.reindex(index=ORDER, columns=ORDER, fill_value=0)
    cm = cm.loc[(cm.sum(axis=1) > 0), (cm.sum(axis=0) > 0)]
    print(cm.to_string())

    diff = a != b
    print(f"\n두 라벨이 다른 쌍: {int(diff.sum())}건")
    pairs = pd.DataFrame({"번호": nums[diff], "첫 라벨": a[diff], "재라벨": b[diff]})
    if len(pairs):
        print(pairs.to_string(index=False))

    # 규칙 문서 §5 미달 처리용: P9 제외, 불일치 쌍이 가장 많이 걸린 유형, 동률이면 코드 번호가 앞선 유형
    counts = {}
    for x, y in zip(a[diff], b[diff]):
        for c in {x, y}:
            if c != "P9":
                counts[c] = counts.get(c, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], ORDER.index(kv[0])))
    print("\n불일치 쌍이 걸린 유형(P9 제외, 건수 내림차순·동률은 코드 번호순)")
    for c, v in ranked:
        print(f"  {c}: {v}건")
    if ranked and k < THRESHOLD:
        print(f"→ 미달 시 경계 규칙을 정리할 유형: {ranked[0][0]}")

    print("\n유형별 일치(첫 라벨 기준)")
    for c in ORDER:
        m = a == c
        if m.sum():
            print(f"  {c}: 첫 라벨 {int(m.sum())}건 중 재라벨도 같은 유형 {int(np.sum(b[m] == c))}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())