"""3단계 결과 분석 (규칙 문서 §5~§7, §8). hold-out 평가(eval_hold.py) 뒤에 실행한다. 규칙은 고치지 않는다.

  python tools/stage3_results.py [--freeze-commit <해시> --rules-sha <12자>]

만드는 것 (원문 없음, 건수·비율만 outputs/tables/stage3_results_*.csv 로 저장)
  1) 유형별 헤드라인 비중: 가중(weight_all, 층화 부트스트랩 95% 구간) + 비가중(Wilson). 분모는 P9 포함 전체 라벨 건수
  2) H1 (P1 가중 비중이 P9 제외 다른 모든 유형보다 높은가, 점추정), H2 (P6a 가중 비중 >= 10%, 점추정)
  3) H3 (탐색적): freight_sum 상위·하위 3분위의 배송비 언급 비율(비가중 주, weight_all 가중은 참고), 방향만
  4) §7 교차분석: freight_sum 3분위 x 유형(주), n_items·n_sellers 1 vs 2+(부). 분기 열이 있으면 같이 계산
  5) 민감도 (§8): 2018-08 제외, 2018-07·08 제외 (정식 재계산: 대상 6,400건에서 해당 월을 빼고 층 모집단 건수를 다시 센 뒤 남은 표본으로 재가중.
     2026-10-30 수정. 이전 버전은 층 모집단 건수 N_h를 그대로 두는 근사였음, D-35)
  6) P6b를 도착 전 응답 / 도착 후 응답으로 분리
  7) 규칙 precision·recall의 가중(weight_all) 참고값과 비가중 차이 (--freeze-commit/--rules-sha를 주면)

고정값: 부트스트랩 2,000회, 시드 20261029 (이 스크립트를 처음 돌리기 전에 정함).
공식 라벨: dev 1~50은 재라벨(v1), 51~204는 첫 라벨, hold-out 106건은 첫 라벨. P9a·P9b는 P9로 합치고 서브태그 건수는 따로 적는다.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAPPING = Path("data/processed/stage3/stage3_mapping.csv")
CROSS = Path("data/processed/stage3/stage3_cross_vars_6400__open_after_labeling.csv")
LAB_DEV = Path("outputs/labels/stage3_labels_dev.csv")
LAB_HOLD = Path("outputs/labels/stage3_labels_hold.csv")
TRANS_HOLD = Path("data/interim/stage3/translations_hold.csv")
TARGET = Path("data/processed/stage3_target_6400.parquet")  # 민감도용 층별 모집단 월 건수(원문 열은 읽지 않음)
OUT_DIR = Path("outputs/tables")
TYPES = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b", "P9"]
SEED, N_BOOT = 20261029, 2000


def tob(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "t", "y", "yes"])


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def load_labels():
    d = pd.read_csv(LAB_DEV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    d["n"] = d["label_order"].astype(int)
    d = d[((d.n <= 50) & (d["pass"] == "relabel")) | ((d.n > 50) & (d["pass"] == "first"))]
    h = pd.read_csv(LAB_HOLD, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert (h["pass"] == "first").all()
    lab = pd.concat([d.drop(columns="n"), h], ignore_index=True)
    assert (lab.codebook_ver == "v1").all() and (lab.label_main != "").all(), "v1이 아니거나 빈 라벨"
    assert lab.review_id.is_unique and len(lab) == 310, f"공식 라벨은 310건이어야 함({len(lab)})"
    return lab


def strat_boot_shares(df, w_col, cats, n_boot, seed):
    """층화 부트스트랩: 층 안에서 같은 크기로 복원추출, 층 가중치는 유지. cats별 가중 비중의 2.5·97.5 백분위."""
    rng = np.random.default_rng(seed)
    y = np.stack([(df["type"] == c).to_numpy() for c in cats], axis=1).astype(float)
    w = df[w_col].to_numpy()
    groups = [np.flatnonzero(df["stratum"].to_numpy() == s) for s in df["stratum"].unique()]
    res = np.empty((n_boot, len(cats)))
    for b in range(n_boot):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        res[b] = (w[idx, None] * y[idx]).sum(0) / w[idx].sum()
    return np.percentile(res, 2.5, axis=0), np.percentile(res, 97.5, axis=0)


def shares_table(df, w_col, label, n_boot, seed):
    cats = TYPES
    w = df[w_col].to_numpy()
    rows = []
    lo, hi = strat_boot_shares(df, w_col, cats, n_boot, seed)
    for i, c in enumerate(cats):
        m = (df["type"] == c).to_numpy()
        k, n = int(m.sum()), len(df)
        wl, wh = wilson(k, n)
        rows.append({"set": label, "type": c, "n": k, "n_total": n,
                     "unweighted": k / n, "unw_lo": wl, "unw_hi": wh,
                     "weighted": float(w[m].sum() / w.sum()), "w_lo": lo[i], "w_hi": hi[i]})
    return pd.DataFrame(rows)


def reweight(df, drop_mask, pop_N):
    """규칙 문서 §8 정식 재계산: 층 모집단 건수를 해당 월을 뺀 값(pop_N)으로 바꾸고, n_h는 남은 표본 건수로.
    모집단이 0이 된 층은 표본도 0이어야 한다(assert). 모집단이 남았는데 표본이 0인 층이 생기면 중단."""
    keep = df[~drop_mask].copy()
    keep["n_h2"] = keep.groupby("stratum")["review_id"].transform("size")
    keep["N_h2"] = keep["stratum"].map(pop_N).fillna(0)
    assert (keep["N_h2"] > 0).all(), "남은 표본이 있는데 모집단이 0인 층이 있음"
    lost = set(pop_N[pop_N > 0].index) - set(keep["stratum"])
    assert not lost, f"모집단은 남았는데 표본이 0이 된 층: {lost}"
    keep["w2"] = keep["N_h2"] / keep["n_h2"]
    dropped_strata = set(df["stratum"]) - set(keep["stratum"])
    return keep, dropped_strata


def newcombe(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-commit")
    ap.add_argument("--rules-sha")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mp = pd.read_csv(MAPPING, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for c in ("N_h", "n_h", "weight_all"):
        mp[c] = mp[c].astype(float)
    cr = pd.read_csv(CROSS, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for c in ("freight_sum", "price_sum", "n_items", "n_sellers"):
        cr[c] = cr[c].astype(float)

    lab = load_labels()
    lab["type"] = lab["label_main"].replace({"P9a": "P9", "P9b": "P9"})
    sub_p9 = lab.loc[lab.label_main.isin(["P9a", "P9b"]), "label_main"].value_counts().to_dict()
    df = lab.merge(mp, on="review_id", how="left", validate="1:1", suffixes=("", "_map"))
    assert df["stratum"].notna().all() and (df["split"].isin(["dev", "hold"])).all(), "mapping에 없는 라벨이 있음"
    assert (df["label_order_map"] == df["label_order"]).all() if "label_order_map" in df else True
    n_split = df["split"].value_counts().to_dict()
    assert n_split == {"dev": 204, "hold": 106}, n_split
    assert np.isclose(df["weight_all"].sum(), 6400), f"weight_all 합이 6,400이 아님: {df['weight_all'].sum()}"
    assert np.allclose(df["weight_all"], df["N_h"] / df["n_h"]), "weight_all != N_h/n_h"
    print(f"[ok] 라벨 310건(dev 204 / hold 106), weight_all 합 {df['weight_all'].sum():.1f}, weight_all = N_h/n_h")
    print(f"층 {df['stratum'].nunique()}개. 층 이름(값 아님, 분기 열이 있는지 확인용):", sorted(df['stratum'].unique())[:12])
    print("P9 서브태그 건수:", sub_p9)

    # ---------- 1) 헤드라인 비중, H1, H2
    sh = shares_table(df, "weight_all", "all310", a.n_boot, a.seed)
    print("\n[1] 헤드라인 비중 (분모 = P9 포함 라벨 310건). weighted = weight_all 가중, 구간 = 층화 부트스트랩")
    pr = sh.copy()
    for c in ("unweighted", "unw_lo", "unw_hi", "weighted", "w_lo", "w_hi"):
        pr[c] = (pr[c] * 100).round(1)
    print(pr[["type", "n", "unweighted", "unw_lo", "unw_hi", "weighted", "w_lo", "w_hi"]].to_string(index=False))
    sh.to_csv(OUT_DIR / "stage3_results_shares.csv", index=False, encoding="utf-8-sig")

    nonp9 = sh[sh.type != "P9"].set_index("type")["weighted"]
    top = nonp9.idxmax()
    others = nonp9.drop("P1").max()
    h1 = nonp9["P1"] > others
    print(f"\nH1 (P1 가중 비중이 P9 제외 다른 모든 유형보다 높음, 점추정): P1 {nonp9['P1']*100:.1f}% / 다음 {nonp9.drop('P1').idxmax()} {others*100:.1f}% → {'지지' if h1 else '기각'} (1위: {top})")
    h2v = float(sh.set_index("type").loc["P6a", "weighted"])
    lo2, hi2 = sh.set_index("type").loc["P6a", ["w_lo", "w_hi"]]
    print(f"H2 (P6a 가중 비중 >= 10%, 점추정): {h2v*100:.1f}% [{lo2*100:.1f}, {hi2*100:.1f}] → {'지지' if h2v >= 0.10 else '기각'}"
          + ("  (구간이 10%를 걸침: 결과 문서에 그대로 적기)" if lo2 < 0.10 <= hi2 or hi2 >= 0.10 > lo2 else ""))
    p9 = sh.set_index("type").loc["P9"]
    print(f"P9 (따로 크게 보고): n={int(p9['n'])}, 가중 {p9['weighted']*100:.1f}% [{p9['w_lo']*100:.1f}, {p9['w_hi']*100:.1f}], 비가중 {p9['unweighted']*100:.1f}%")

    # ---------- 3) H3 + 4) 교차분석
    df = df.merge(cr, on="review_id", how="left", validate="1:1")
    assert df["freight_tercile"].notna().all(), "교차 변수에 없는 라벨이 있음"
    terc_mean = df.groupby("freight_tercile")["freight_sum"].mean().sort_values()
    low_t, up_t = terc_mean.index[0], terc_mean.index[-1]
    all_t = cr.assign(f=cr["freight_sum"]).groupby("freight_tercile")["f"].agg(["size", "mean"]).sort_values("mean")
    print("\n[§7] 6,400건 전체의 3분위 건수(기대 2,137 / 2,130 / 2,133, 낮은 분위부터):", all_t["size"].tolist())
    df["freight_ment"] = df["mentions_freight_cost"].astype(str).str.strip().str.upper()
    df["ment_true"] = df["freight_ment"].eq("TRUE")
    print("mentions_freight_cost 값 분포:", df["freight_ment"].value_counts().to_dict())
    rows = []
    for t in terc_mean.index:
        g = df[df.freight_tercile == t]
        k, n = int(g.ment_true.sum()), len(g)
        l, h_ = wilson(k, n)
        rows.append({"tercile": t, "n": n, "mention_true": k, "rate": k / n, "lo": l, "hi": h_,
                     "U": int((g.freight_ment == "U").sum()),
                     "weighted_rate": float((g.weight_all * g.ment_true).sum() / g.weight_all.sum())})
    h3 = pd.DataFrame(rows)
    print("\n[3] H3 (탐색적, 라벨링한 310건 기준, 비가중 주 / weight_all 가중은 참고, U는 False로 합침)")
    print(h3.assign(rate=(h3.rate * 100).round(1), lo=(h3.lo * 100).round(1), hi=(h3.hi * 100).round(1),
                    weighted_rate=(h3.weighted_rate * 100).round(1)).to_string(index=False))
    h3.to_csv(OUT_DIR / "stage3_results_h3.csv", index=False, encoding="utf-8-sig")
    u, l = h3.set_index("tercile").loc[up_t], h3.set_index("tercile").loc[low_t]
    if int(u.mention_true + l.mention_true) < 10 or u.rate == l.rate:
        verdict = "판단불가(상·하위 언급 건수 합 10건 미만이거나 두 비율이 같음)"
    else:
        d, dl, dh = newcombe(int(u.mention_true), int(u.n), int(l.mention_true), int(l.n))
        verdict = (f"{'방향 일치' if u.rate > l.rate else '방향 불일치'} (상위 {u.rate*100:.1f}% - 하위 {l.rate*100:.1f}% = "
                   f"{d*100:+.1f}%p, Newcombe 구간 [{dl*100:+.1f}, {dh*100:+.1f}]) → 약한 증거, 방향 관찰로만 기록")
    print(f"H3 판정 (상위 {up_t} vs 하위 {low_t}): {verdict}")

    print("\n[4] 교차분석 (가중 비중, weight_all; 칸 건수 병기. 칸 n<15는 불안정)")
    def cross(col, name):
        out = []
        for gval, g in df.groupby(col):
            for c in TYPES:
                m = g["type"] == c
                out.append({"cross": name, "group": gval, "type": c, "n": int(m.sum()), "n_group": len(g),
                            "weighted": float(g.loc[m, "weight_all"].sum() / g["weight_all"].sum())})
        t = pd.DataFrame(out)
        piv = t.pivot(index="type", columns="group", values="weighted").reindex(TYPES) * 100
        cnt = t.pivot(index="type", columns="group", values="n").reindex(TYPES)
        print(f"\n{name} (가중 %, 괄호 = 칸 건수)")
        print(piv.round(1).astype(str).add(" (").add(cnt.astype(str)).add(")").to_string())
        return t
    ct = [cross("freight_tercile", "주: freight_sum 3분위")]
    ct.append(cross("n_items_grp", "부: n_items"))
    ct.append(cross("n_sellers_grp", "부: n_sellers"))
    # 층 이름 앞부분(예: 2017Q1_1 -> 2017Q1)을 분기로 사용. 층 정의(규칙 문서 §2)로 확인할 것
    df["quarter"] = df["stratum"].astype(str).str.split("_").str[0]
    ct.append(cross("quarter", "주: 분기(층 이름 앞부분)"))
    pd.concat(ct).to_csv(OUT_DIR / "stage3_results_cross.csv", index=False, encoding="utf-8-sig")
    print("(위 4개 이외의 교차는 '사후 탐색'이며 다중비교 보정을 하지 않았다)")

    # ---------- 5) 민감도
    print("\n[5] 민감도 (§8 정식 재계산: 대상 6,400건에서 해당 월을 빼고 층 모집단 건수를 다시 센 뒤 남은 표본으로 재가중)")
    pop = pd.read_parquet(TARGET, columns=["review_id", "stratum", "is_aug_2018", "is_jul_aug_2018"])
    assert len(pop) == 6400 and pop.review_id.is_unique, "대상 파일이 6,400건이 아님"
    n_all = pop.groupby("stratum").size()
    assert (n_all.reindex(df.groupby("stratum")["N_h"].first().index) == df.groupby("stratum")["N_h"].first()).all(), \
        "대상 파일의 층별 건수가 mapping의 N_h와 다름"
    sens = [sh.assign(**{"set": "all310"})]
    for flag, name in (("is_aug_2018", "2018-08 제외"), ("is_jul_aug_2018", "2018-07·08 제외")):
        mask = tob(df[flag])
        pop_N = pop[pop[flag].astype(int) == 0].groupby("stratum").size()
        print(f"{name}: 모집단 {int(pop_N.sum())}건 (제외 {6400 - int(pop_N.sum())}건)")
        keep, dropped = reweight(df, mask, pop_N)
        s2 = shares_table(keep, "w2", name, a.n_boot, a.seed)
        sens.append(s2)
        p1, p6a = s2.set_index("type").loc["P1", "weighted"], s2.set_index("type").loc["P6a", "weighted"]
        print(f"{name}: 제외 {int(mask.sum())}건, 남은 표본 {len(keep)}건, 표본이 0이 된 층 {len(dropped)}개 → P1 {p1*100:.1f}%, P6a {p6a*100:.1f}% "
              f"(H1 {'지지' if s2[s2.type != 'P9'].set_index('type')['weighted'].idxmax() == 'P1' else '기각'}, H2 {'지지' if p6a >= 0.10 else '기각'})")
    pd.concat(sens).to_csv(OUT_DIR / "stage3_results_sensitivity.csv", index=False, encoding="utf-8-sig")

    # ---------- 6) P6b 도착 전/후
    p6b = df[df["type"] == "P6b"].copy()
    print("\nanswered_before_delivery 원값(P6b):", p6b["answered_before_delivery"].value_counts().to_dict())
    p6b["before"] = tob(p6b["answered_before_delivery"])
    n_b, n_a = int(p6b.before.sum()), int((~p6b.before).sum())
    w_b, w_a = float(p6b.loc[p6b.before, "weight_all"].sum() / df.weight_all.sum()), float(p6b.loc[~p6b.before, "weight_all"].sum() / df.weight_all.sum())
    print(f"\n[6] P6b 분리: 도착 전 응답 {n_b}건(가중 {w_b*100:.1f}%), 도착 후 응답 {n_a}건(가중 {w_a*100:.1f}%) / P6b 전체 {len(p6b)}건. "
          "도착 전 응답은 '고객 미수령'으로 단정하지 않는다")
    pd.DataFrame([{"split": "before", "n": n_b, "weighted": w_b}, {"split": "after", "n": n_a, "weighted": w_a}]).to_csv(
        OUT_DIR / "stage3_results_p6b_split.csv", index=False, encoding="utf-8-sig")

    # ---------- 7) 규칙 precision·recall 가중 참고값
    if a.freeze_commit and a.rules_sha:
        import hold_guard
        hold_guard.assert_frozen(a.freeze_commit, a.rules_sha)
        import kw_rules
        tx = pd.read_csv(TRANS_HOLD, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        hd = df[df.split == "hold"].merge(tx[["review_id", "text_pt"]], on="review_id", validate="1:1")
        assert len(hd) == 106
        hd["rule"] = hd["text_pt"].map(kw_rules.classify)
        rows = []
        for c in TYPES[:-2] + ["P6b"]:
            tp = hd[(hd.rule == c) & (hd.type == c)]
            pr_n, pr_w = (hd.rule == c).sum(), hd.loc[hd.rule == c, "weight_all"].sum()
            rc_n, rc_w = (hd.type == c).sum(), hd.loc[hd.type == c, "weight_all"].sum()
            rows.append({"type": c,
                         "precision": len(tp) / pr_n if pr_n else float("nan"),
                         "precision_w": tp.weight_all.sum() / pr_w if pr_w else float("nan"),
                         "recall": len(tp) / rc_n if rc_n else float("nan"),
                         "recall_w": tp.weight_all.sum() / rc_w if rc_w else float("nan")})
        rw = pd.DataFrame(rows)
        rw["precision_diff"] = rw.precision_w - rw.precision
        rw["recall_diff"] = rw.recall_w - rw.recall
        print("\n[7] 규칙 precision·recall: 비가중(주) vs weight_all 가중(참고). 차이가 크면 한계에 적는다")
        print(rw.round(2).to_string(index=False))
        rw.to_csv(OUT_DIR / "stage3_results_rule_weighted.csv", index=False, encoding="utf-8-sig")
    else:
        print("\n[7] 건너뜀: --freeze-commit, --rules-sha를 주면 규칙 가중 참고값을 계산한다")
    print("\n저장: outputs/tables/stage3_results_*.csv (건수·비율만, 원문 없음). 규칙은 고치지 않았다.")


if __name__ == "__main__":
    main()
