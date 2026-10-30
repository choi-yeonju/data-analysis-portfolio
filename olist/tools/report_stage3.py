"""[교차검증용 두 번째 구현] 공식 집계는 tools/stage3_results.py다(decisions D-34).
이 스크립트에서 인용하는 것은 H1 보조 지표(재표본 중 P1 최다 비율, 차이 구간)와 비가중 교차 건수표뿐이다.
§8 8월 제외 민감도 출력(stage3_final_sensitivity_aug.csv)은 근사이며, 공식 값은 D-35의 정식 재계산(stage3_results.py)이다. 인용하지 않는다.

3단계 최종 집계 (규칙 문서 §6~§8). hold-out 라벨링과 규칙 평가가 모두 끝난 뒤에 실행한다. 실행은 olist 폴더, .venv 에서.

  python tools\\report_stage3.py                 # 화면 출력 + outputs/tables/stage3_final_*.csv 저장
  python tools\\report_stage3.py --seed 20261029 --n-boot 2000

입력(모두 읽기만 한다. 리뷰 원문은 읽지 않는다)
  outputs/labels/stage3_labels_dev.csv       공식 라벨 = dev 1~50 재라벨(v1) + 51~204 첫 라벨(v1). v0는 쓰지 않는다
  outputs/labels/stage3_labels_hold.csv      hold-out 첫 라벨(v1)
  data/processed/stage3/stage3_mapping.csv   층, N_h, n_h, weight_all, answered_before_delivery, is_aug_2018 (표본 310건)
  data/processed/stage3/stage3_cross_vars_6400__open_after_labeling.csv   freight_sum 등 (라벨링이 끝난 뒤에만 연다)

계산
  헤드라인: 가중 수동 라벨 비중(weight_all). 분모는 P9를 포함한 전체. P9a·P9b는 P9로 합치고 P9는 따로 크게 보고한다.
  구간: 층 안에서 다시 뽑는 층화 부트스트랩(층별 n_h개를 복원추출), 2.5·97.5 백분위, 시드 고정.
  H1: P1 가중 비중이 P9를 뺀 다른 모든 유형보다 높은가 (점추정).
  H2: P6a 가중 비중이 10% 이상인가 (점추정, 구간이 10%에 걸리면 그대로 적는다).
  H3(탐색): freight_sum 상위 분위의 배송비 언급 비율이 하위보다 높은가 (비가중, U는 False로 합침, 방향만).
            분위 경계 q1=15.94, q2=28.19 (하 <= q1 < 중 <= q2 < 상), 상·하 언급 건수 합 10건 미만이거나 비율이 같으면 판단불가.
  §7 교차분석: freight_sum 3분위, 분기(주), n_items, n_sellers(부). 나머지는 "사후 탐색, 다중비교 보정 없음".
  §8 8월 제외 민감도, P6b 도착 전/후 분리(answered_before_delivery).
이 스크립트는 규칙·코드북·가설 기준을 바꾸지 않는다.
"""
import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LAB_DEV = Path("outputs/labels/stage3_labels_dev.csv")
LAB_HOLD = Path("outputs/labels/stage3_labels_hold.csv")
MAPPING = Path("data/processed/stage3/stage3_mapping.csv")
CROSS = Path("data/processed/stage3/stage3_cross_vars_6400__open_after_labeling.csv")
OUT_DIR = Path("outputs/tables")
TYPES = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b", "P9"]
Q1, Q2 = 15.94, 28.19
H2_CUT = 0.10


def die(msg):
    print("중단:", msg)
    sys.exit(1)


def rd(p):
    p = Path(p)
    if not p.exists():
        die(f"{p} 없음")
    return pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def to_bool(s):
    return s.astype(str).str.strip().str.lower().isin(["1", "true", "t", "yes", "y"])


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def newcombe_diff(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def load_official():
    dev = rd(LAB_DEV)
    dev["n"] = dev["label_order"].astype(int)
    off = dev[((dev["n"] <= 50) & (dev["pass"] == "relabel")) | ((dev["n"] > 50) & (dev["pass"] == "first"))].copy()
    if len(off) != 204 or off["review_id"].duplicated().any():
        die(f"dev 공식 라벨이 204건이 아니거나 중복(현재 {len(off)}건)")
    if not (off["codebook_ver"] == "v1").all():
        die("dev 공식 라벨에 v1이 아닌 행이 있음")
    off["source"] = "dev"
    hold = rd(LAB_HOLD)
    if len(hold) != 106 or hold["review_id"].duplicated().any():
        die(f"hold-out 라벨이 106건이 아니거나 중복(현재 {len(hold)}건)")
    if not ((hold["pass"] == "first").all() and (hold["codebook_ver"] == "v1").all()):
        die("hold-out 라벨은 첫 라벨(v1)만이어야 함")
    hold["source"] = "hold"
    cols = ["review_id", "label_main", "label_sub", "mentions_freight_cost", "source"]
    lab = pd.concat([off[cols], hold[cols]], ignore_index=True)
    if (lab["label_main"] == "").any():
        die("빈 label_main이 있음")
    lab["sub_raw"] = lab["label_main"]
    lab["main"] = lab["label_main"].replace({"P9a": "P9", "P9b": "P9"})
    if not set(lab["main"]) <= set(TYPES):
        die(f"알 수 없는 유형: {set(lab['main']) - set(TYPES)}")
    return lab


def attach(lab):
    mp = rd(MAPPING)
    need = ["review_id", "split", "stratum", "N_h", "n_h", "weight_all", "answered_before_delivery", "is_aug_2018"]
    miss = [c for c in need if c not in mp.columns]
    if miss:
        die(f"mapping에 없는 열: {miss}")
    mp = mp[need].copy()
    for c in ["N_h", "n_h", "weight_all"]:
        mp[c] = mp[c].astype(float)
    if mp["review_id"].duplicated().any() or set(mp["review_id"]) != set(lab["review_id"]):
        die("mapping과 라벨의 review_id 집합이 다름(310건이어야 함)")
    df = lab.merge(mp, on="review_id", validate="1:1")
    if not ((df["source"] == df["split"].map({"dev": "dev", "hold": "hold"})).all()):
        die("라벨 출처(dev/hold)와 mapping의 split이 다름")
    g = df.groupby("stratum")
    if not (g.size().eq(g["n_h"].first())).all():
        die("층별 라벨 건수가 mapping의 n_h와 다름")
    if not np.isclose(g["N_h"].first().sum(), 6400, atol=0.5):
        die(f"N_h 합이 6,400이 아님({g['N_h'].first().sum()})")
    if not np.isclose(df["weight_all"].sum(), 6400, atol=1.0):
        die(f"weight_all 합이 6,400이 아님({df['weight_all'].sum():.1f})")
    cr = rd(CROSS)
    need2 = ["review_id", "freight_sum", "n_items_grp", "n_sellers_grp"]
    miss = [c for c in need2 if c not in cr.columns]
    if miss:
        die(f"cross_vars에 없는 열: {miss}")
    cr = cr[need2].copy()
    cr["freight_sum"] = cr["freight_sum"].astype(float)
    if cr["review_id"].duplicated().any() or len(cr) != 6400:
        die(f"cross_vars가 6,400건이 아니거나 review_id 중복({len(cr)}건)")
    df = df.merge(cr, on="review_id", how="left", validate="1:1")
    if df["freight_sum"].isna().any():
        die("표본 일부가 cross_vars에 없음")
    df["tercile"] = np.where(df["freight_sum"] <= Q1, "하", np.where(df["freight_sum"] <= Q2, "중", "상"))
    cr["tercile"] = np.where(cr["freight_sum"] <= Q1, "하", np.where(cr["freight_sum"] <= Q2, "중", "상"))
    print(f"[점검] 6,400건 분위 건수(하/중/상): {cr['tercile'].value_counts().reindex(['하', '중', '상']).tolist()} (규칙 문서 기대 2,137 / 2,130 / 2,133)")
    df["aug"] = to_bool(df["is_aug_2018"])
    df["before"] = to_bool(df["answered_before_delivery"])
    m = df["stratum"].map(lambda s: re.search(r"(20\d{2})\D*Q?(\d)", str(s)))
    df["quarter"] = m.map(lambda x: f"{x.group(1)}Q{x.group(2)}" if x else None)
    return df


def shares(df, w="weight_all"):
    tot = df[w].sum()
    return pd.Series({t: df.loc[df["main"] == t, w].sum() / tot for t in TYPES})


def boot_shares(df, n_boot, seed):
    rng = np.random.default_rng(seed)
    tidx = df["main"].map({t: i for i, t in enumerate(TYPES)}).to_numpy()
    w = df["weight_all"].to_numpy()
    groups = [np.flatnonzero((df["stratum"] == s).to_numpy()) for s in df["stratum"].unique()]
    out = np.empty((n_boot, len(TYPES)))
    for b in range(n_boot):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        out[b] = np.bincount(tidx[idx], weights=w[idx], minlength=len(TYPES)) / w[idx].sum()
    return pd.DataFrame(out, columns=TYPES)


def fmt_pct(x):
    return f"{100 * x:5.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--n-boot", type=int, default=2000)
    a = ap.parse_args()

    lab = load_official()
    df = attach(lab)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"공식 라벨 310건 (dev {int((df['source'] == 'dev').sum())} + hold-out {int((df['source'] == 'hold').sum())}), "
          f"층 {df['stratum'].nunique()}개, weight_all 합 {df['weight_all'].sum():.0f}, 범위 {df['weight_all'].min():.2f}~{df['weight_all'].max():.2f}")
    print(f"P9 서브태그 건수: P9a {int((df['sub_raw'] == 'P9a').sum())}, P9b {int((df['sub_raw'] == 'P9b').sum())}")

    # ---- 헤드라인: 가중 비중
    sh = shares(df)
    bs = boot_shares(df, a.n_boot, a.seed)
    lo, hi = bs.quantile(0.025), bs.quantile(0.975)
    raw_n = df["main"].value_counts().reindex(TYPES).fillna(0).astype(int)
    tab = pd.DataFrame({"n": raw_n, "비가중_비중": raw_n / len(df), "가중_비중": sh, "구간_하": lo, "구간_상": hi})
    print(f"\n[헤드라인] 가중 수동 라벨 비중 (분모 = P9 포함 전체, 층화 부트스트랩 {a.n_boot}회, 시드 {a.seed}, 95%)")
    for t, r in tab.iterrows():
        print(f"  {t:>3}: n={int(r['n']):3d}  비가중 {fmt_pct(r['비가중_비중'])}  가중 {fmt_pct(r['가중_비중'])}  [{fmt_pct(r['구간_하'])}, {fmt_pct(r['구간_상'])}]"
              + ("   <- P9는 따로 크게 보고" if t == "P9" else ""))
    tab.to_csv(OUT_DIR / "stage3_final_shares.csv", encoding="utf-8-sig")

    # ---- H1
    others = [t for t in TYPES if t not in ("P1", "P9")]
    top_other = max(others, key=lambda t: sh[t])
    h1 = sh["P1"] > max(sh[t] for t in others)
    ratio_max = float((bs["P1"] > bs[others].max(axis=1)).mean())
    print(f"\n[H1] P1 가중 비중 {fmt_pct(sh['P1'])} vs P9 제외 최대 다른 유형 {top_other} {fmt_pct(sh[top_other])} -> "
          f"{'점추정 기준 지지(P1이 최다)' if h1 else '점추정 기준 기각(P1이 최다가 아님)'}")
    print(f"      참고: 부트스트랩 재표본 중 P1이 최다인 비율 {100 * ratio_max:.1f}%")
    d1 = bs["P1"] - bs[others].max(axis=1)
    print(f"      참고: P1 - 최대 다른 유형 차이의 95% 구간 [{fmt_pct(d1.quantile(.025))}, {fmt_pct(d1.quantile(.975))}]")

    # ---- H2
    h2 = sh["P6a"] >= H2_CUT
    straddle = lo["P6a"] <= H2_CUT <= hi["P6a"]
    print(f"\n[H2] P6a 가중 비중 {fmt_pct(sh['P6a'])} [{fmt_pct(lo['P6a'])}, {fmt_pct(hi['P6a'])}] (기준 10%) -> "
          f"{'점추정 기준 지지' if h2 else '점추정 기준 기각'}" + (", 구간이 10%에 걸림(그대로 기재)" if straddle else ""))
    print(f"      P6a 원시 건수 {int(raw_n['P6a'])}건 / 310건. 이 유형은 재라벨 kappa 검증이 약했음(D-32).")

    # ---- H3 (탐색, 비가중, U는 False)
    df["mention"] = df["mentions_freight_cost"].eq("True")
    df["u"] = df["mentions_freight_cost"].eq("U")
    rows = []
    for t in ["하", "중", "상"]:
        g = df[df["tercile"] == t]
        rows.append({"분위": t, "n": len(g), "언급(True)": int(g["mention"].sum()), "U": int(g["u"].sum()),
                     "비가중 비율": g["mention"].mean(),
                     "가중 비율(참고)": g.loc[g["mention"], "weight_all"].sum() / g["weight_all"].sum()})
    h3t = pd.DataFrame(rows).set_index("분위")
    print("\n[H3 탐색] freight_sum 3분위별 배송비 언급 (U는 False로 합침, 비가중이 주 지표)")
    print(h3t.to_string(float_format=lambda x: f"{x:.3f}"))
    up, lowg = h3t.loc["상"], h3t.loc["하"]
    total_ment = int(up["언급(True)"] + lowg["언급(True)"])
    if total_ment < 10 or math.isclose(up["비가중 비율"], lowg["비가중 비율"]):
        verdict = "판단불가"
    else:
        verdict = "방향 일치" if up["비가중 비율"] > lowg["비가중 비율"] else "방향 불일치"
    msg = f"[H3] 상 {up['비가중 비율']:.3f} vs 하 {lowg['비가중 비율']:.3f}, 상·하 언급 합 {total_ment}건 -> {verdict}"
    if total_ment >= 1 and int(up["n"]) > 0 and int(lowg["n"]) > 0:
        d, dl, du = newcombe_diff(int(up["언급(True)"]), int(up["n"]), int(lowg["언급(True)"]), int(lowg["n"]))
        msg += f" (차이 {d:+.3f}, 95% 구간 [{dl:+.3f}, {du:+.3f}], 유의성 판정 없음, 약한 증거)"
    print(msg)
    print("      분기마다 freight_sum 분포가 다르면 분기 구성의 영향이 남음(규칙 문서 한계). 분위별 U 건수를 함께 적을 것.")
    h3t.to_csv(OUT_DIR / "stage3_final_h3.csv", encoding="utf-8-sig")

    # ---- §7 교차분석 (건수 + 행 비율, 비가중)
    print("\n[§7 교차분석] 비가중 건수 (행 = 구분, 열 = 유형). 주: freight_sum 분위, 분기. 부: n_items, n_sellers. 나머지는 사후 탐색.")
    blocks = [("freight 3분위(주)", "tercile"), ("분기(주)", "quarter"), ("n_items(부)", "n_items_grp"), ("n_sellers(부)", "n_sellers_grp")]
    allct = []
    for name, col in blocks:
        if df[col].isna().any():
            print(f"  {name}: 분기를 층 이름에서 읽지 못함. 층 이름 목록: {sorted(df['stratum'].unique())}")
            continue
        ct = pd.crosstab(df[col], df["main"]).reindex(columns=TYPES, fill_value=0)
        ct["합"] = ct.sum(axis=1)
        print(f"\n  <{name}>")
        print(ct.to_string())
        long = ct.drop(columns="합").stack().rename("n").reset_index()
        long.columns = ["구분값", "유형", "n"]
        long.insert(0, "교차", name)
        allct.append(long)
    if allct:
        pd.concat(allct).to_csv(OUT_DIR / "stage3_final_cross.csv", index=False, encoding="utf-8-sig")
    print("  (이 표들 외의 교차는 \"사후 탐색, 다중비교 보정 안 함\"으로 표기)")

    # ---- §8 8월 제외 민감도 (근사)
    sub = df[~df["aug"]]
    print(f"\n[§8 민감도] 2018-08 구매 제외: {int(df['aug'].sum())}건 제외, {len(sub)}건 사용. 주 결과는 위의 전체 기준.")
    print("  주의: 8월 제외 후 N_h를 다시 구할 값(층별 8월 건수)이 없어 가중치는 원래 값을 유지하고 분모만 다시 맞춘 근사다.")
    ss = shares(sub)
    sens = pd.DataFrame({"전체_가중": sh, "8월제외_가중(근사)": ss, "8월제외_비가중": sub["main"].value_counts(normalize=True).reindex(TYPES).fillna(0)})
    print(sens.to_string(float_format=lambda x: f"{100 * x:.1f}%"))
    print(f"  H1(8월 제외, 근사): P1 {fmt_pct(ss['P1'])} vs 최대 {max(others, key=lambda t: ss[t])} {fmt_pct(max(ss[t] for t in others))} / H2: P6a {fmt_pct(ss['P6a'])}")
    sens.to_csv(OUT_DIR / "stage3_final_sensitivity_aug.csv", encoding="utf-8-sig")

    # ---- P6b 도착 전/후
    p6 = df[df["main"] == "P6b"]
    nb, na = int(p6["before"].sum()), int((~p6["before"]).sum())
    wtot = p6["weight_all"].sum()
    print(f"\n[P6b 분리] P6b {len(p6)}건: 도착 전 응답 {nb}건, 도착 후 응답 {na}건 "
          f"(가중 도착 전 비중 {100 * p6.loc[p6['before'], 'weight_all'].sum() / wtot:.1f}% / 후 {100 * p6.loc[~p6['before'], 'weight_all'].sum() / wtot:.1f}%)"
          if len(p6) else "\n[P6b 분리] P6b가 0건")
    pd.DataFrame({"구분": ["도착 전 응답", "도착 후 응답"], "n": [nb, na]}).to_csv(OUT_DIR / "stage3_final_p6b_split.csv", index=False, encoding="utf-8-sig")
    print("  P6b는 작성 시점을 확인하기 전에는 \"고객 미수령\"으로 단정하지 않는다(코드북 §1).")

    print(f"\n저장: {OUT_DIR}\\stage3_final_*.csv (건수·비율만, 원문 없음)")
    print("해석 문구: \"코멘트를 남긴 저평점 집단의 불만 구성\"까지만 쓴다. 인과(경보가 놓친 이유)는 쓰지 않는다(§6-2 A).")


if __name__ == "__main__":
    main()
