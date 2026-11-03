"""급증 이벤트 판정 (계획서 5-2).

옛 노트북과 다른 점
- z-score는 '직전' 8주로 계산한다 (shift(1)). 이번 주를 창에 넣으면 z가 (8-1)/√8 ≈ 2.47을
  넘을 수 없어서, z > 2.0 이 사실상 '8주 중 최댓값'이 되어 버린다.
- 표준편차가 0이면 판정하지 않는다 (+1e-9 로 나누지 않음 → 0에서 튀는 가짜 급증 방지).
- ratio >= 5 같은 절대 크기 조건은 쓰지 않는다 (미래 피크에 의존).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_features(
    weekly: pd.DataFrame, z_window: int = 8, mult_window: int = 6
) -> pd.DataFrame:
    """weekly: index=주(월요일), 열 'ratio'. z, 배율, 직전 8주 0 아닌 주 수를 붙인다."""
    out = weekly.copy()
    s = out["ratio"].astype(float)
    prev = s.shift(1)

    rm = prev.rolling(z_window, min_periods=z_window).mean()
    rs = prev.rolling(z_window, min_periods=z_window).std()  # 표본 표준편차
    base = prev.rolling(mult_window, min_periods=mult_window).mean()

    out["z"] = np.where(rs > 0, (s - rm) / rs, np.nan)
    # 직전 6주 평균이 0이고 이번 주가 0보다 크면 배율 = inf (표시만 해 두고 판정은 z가 거름)
    out["multiplier"] = np.where(
        base > 0, s / base, np.where((base == 0) & (s > 0), np.inf, np.nan)
    )
    out["nonzero_prev8"] = (prev > 0).astype(float).rolling(
        z_window, min_periods=z_window
    ).sum()
    return out


def detect_spikes(
    weekly: pd.DataFrame,
    z_thresh: float = 2.0,
    mult_thresh: float = 2.0,
    min_nonzero: int | None = None,
    pub_week: pd.Timestamp | None = None,
    exclude_within_weeks: int = 4,
) -> pd.DataFrame:
    """급증 이벤트 목록. 연속 급증 주는 하나로 합치고 크기는 '시작 주' 값을 쓴다.

    min_nonzero: '직전 8주 중 0 아닌 주 >= 4' 조건. 눌림 검증 후 확정이라 기본은 끔(None).
    pub_week: 주어지면 출간 후 exclude_within_weeks 주 안에 시작한 급증은 뺀다 (메인 규칙).
    """
    f = add_features(weekly)
    flag = (f["z"] > z_thresh) & (f["multiplier"] >= mult_thresh)
    if min_nonzero is not None:
        flag &= f["nonzero_prev8"] >= min_nonzero
    f["flag"] = flag.fillna(False)

    # 연속 구간 묶기
    run_id = (f["flag"] != f["flag"].shift()).cumsum()
    events = []
    for _, block in f[f["flag"]].groupby(run_id[f["flag"]]):
        first = block.iloc[0]
        events.append(
            {
                "start_week": block.index[0],
                "end_week": block.index[-1],
                "n_weeks": len(block),
                "start_z": first["z"],
                "start_multiplier": first["multiplier"],
            }
        )
    ev = pd.DataFrame(
        events,
        columns=["start_week", "end_week", "n_weeks", "start_z", "start_multiplier"],
    )

    if pub_week is not None and not ev.empty:
        cutoff = pd.Timestamp(pub_week) + pd.Timedelta(weeks=exclude_within_weeks)
        ev = ev[ev["start_week"] >= cutoff].reset_index(drop=True)
    return ev
