"""진입 주 이벤트 스터디 (계획서 5-1 절차, 파일럿 첫 이틀).

지표: 그룹별 Σ(-4~-1주) ÷ Σ(-8~-5주). 책별 비율이 아니라 합산 비율이라 -8~-5주가 0인 책도 버리지 않는다.
Go 기준: 200위 밖 진입 그룹의 합산 비율이 책 단위 부트스트랩 95% CI에서 대조군보다 크고, 하한이 Y 이상.
Y 값은 데이터를 보기 전에 PREREGISTRATION.md 에 적고 커밋한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GROUPS = ("out200", "in101_200", "control")  # 200위 밖 진입 / 101~200위 체류 진입 / 비진입 대조군


def window_sums(weekly: pd.DataFrame, entry_week: pd.Timestamp) -> tuple[float, float] | None:
    """(Σ -4~-1주, Σ -8~-5주). 8주가 다 없으면 None. weekly는 진입 직전 주까지 자른 요청(ⓐ)."""
    entry = pd.Timestamp(entry_week)
    weeks_pre4 = [entry - pd.Timedelta(weeks=k) for k in range(1, 5)]
    weeks_pre8 = [entry - pd.Timedelta(weeks=k) for k in range(5, 9)]
    s = weekly["ratio"]
    if not all(w in s.index for w in weeks_pre4 + weeks_pre8):
        return None
    return float(s.loc[weeks_pre4].sum()), float(s.loc[weeks_pre8].sum())


def build_table(books: list[dict]) -> pd.DataFrame:
    """books: [{'book_id', 'group', 'weekly', 'entry_week'}, ...]
    대조군의 entry_week 는 '같은 출간 경과 주의 가상 시점'."""
    rows = []
    for b in books:
        sums = window_sums(b["weekly"], b["entry_week"])
        if sums is None:
            continue
        rows.append({"book_id": b["book_id"], "group": b["group"], "pre4": sums[0], "pre8": sums[1]})
    return pd.DataFrame(rows, columns=["book_id", "group", "pre4", "pre8"])


def pooled_ratio(df: pd.DataFrame) -> float:
    den = df["pre8"].sum()
    return float(df["pre4"].sum() / den) if den > 0 else np.nan


def summarize(table: pd.DataFrame, n_boot: int = 2000, seed: int = 0) -> pd.DataFrame:
    """그룹별 n, 합산 비율, 부트스트랩 95% CI, -8~-5주가 0인 책 비율."""
    rng = np.random.default_rng(seed)
    out = []
    for g in GROUPS:
        sub = table[table["group"] == g].reset_index(drop=True)
        n = len(sub)
        if n == 0:
            out.append({"group": g, "n": 0})
            continue
        boots = [pooled_ratio(sub.iloc[rng.integers(0, n, n)]) for _ in range(n_boot)]
        lo, hi = np.nanpercentile(boots, [2.5, 97.5])
        out.append(
            {
                "group": g,
                "n": n,
                "pooled_ratio": pooled_ratio(sub),
                "ci_low": lo,
                "ci_high": hi,
                "zero_denominator_share": float((sub["pre8"] == 0).mean()),
            }
        )
    return pd.DataFrame(out).set_index("group")


def go_check(table: pd.DataFrame, Y: float, n_boot: int = 2000, seed: int = 0) -> dict:
    """절차 4·5. '미확정'과 'No-Go'는 분모 0 비율·CI 폭을 보고 사람이 가른다."""
    rng = np.random.default_rng(seed)
    a = table[table["group"] == "out200"].reset_index(drop=True)
    c = table[table["group"] == "control"].reset_index(drop=True)
    if len(a) < 10:
        return {"verdict": "판정 불가", "reason": f"200위 밖 진입 그룹 n={len(a)} < 10"}
    if len(c) == 0:
        return {"verdict": "판정 불가", "reason": "대조군 없음"}

    ra, diff = [], []
    for _ in range(n_boot):
        x = pooled_ratio(a.iloc[rng.integers(0, len(a), len(a))])
        y = pooled_ratio(c.iloc[rng.integers(0, len(c), len(c))])
        ra.append(x)
        diff.append(x - y)
    a_lo = float(np.nanpercentile(ra, 2.5))
    d_lo = float(np.nanpercentile(diff, 2.5))
    go = (d_lo > 0) and (a_lo >= Y)
    return {
        "verdict": "Go" if go else "기준 미충족 (No-Go 또는 미확정)",
        "out200_ci_low": a_lo,
        "diff_vs_control_ci_low": d_lo,
        "Y": Y,
    }
