import numpy as np
import pandas as pd

from src import datalab, event_study, spikes


def _weekly(values, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="7D")
    return pd.DataFrame({"ratio": values}, index=idx)


# ── datalab ────────────────────────────────────────────────
def test_missing_days_filled_with_zero():
    resp = {"timeUnit": "date", "results": [{"data": [
        {"period": "2024-01-03", "ratio": 50}, {"period": "2024-01-05", "ratio": 100}]}]}
    d = datalab.to_daily(resp, "2024-01-01", "2024-01-07")
    assert len(d) == 7 and d.sum() == 150 and d.loc["2024-01-01"] == 0


def test_weekly_drops_partial_weeks_and_starts_monday():
    resp = {"timeUnit": "date", "results": [{"data": [{"period": "2024-01-10", "ratio": 1}]}]}
    d = datalab.to_daily(resp, "2024-01-03", "2024-01-23")  # 수요일 ~ 화요일
    w = datalab.daily_to_weekly(d)
    assert list(w.index) == [pd.Timestamp("2024-01-08"), pd.Timestamp("2024-01-15")]
    assert all(ts.day_of_week == 0 for ts in w.index)


def test_keywords():
    assert len(datalab.build_keywords("수족관", "유래혁")) == 4
    assert datalab.build_keywords("수족관", "유래혁", dict_word=True) == ["수족관 유래혁"]
    assert datalab.title_rule("여름") == "exclude"


# ── spikes ─────────────────────────────────────────────────
def test_old_bug_z_capped_at_2_47():
    """이번 주를 창에 넣으면 아무리 튀어도 z ≈ 2.47 이 최대 (옛 노트북 버그 재현)."""
    s = pd.Series([1, 2, 1, 2, 1, 2, 1, 1000.0])
    old_z = (s - s.rolling(8).mean()) / s.rolling(8).std()
    assert abs(old_z.iloc[-1] - 7 / np.sqrt(8)) < 0.01


def test_new_z_not_capped():
    f = spikes.add_features(_weekly([1, 2, 1, 2, 1, 2, 1, 2, 1000.0]))
    assert f["z"].iloc[-1] > 100


def test_zero_std_not_judged():
    f = spikes.add_features(_weekly([0] * 8 + [5.0]))
    assert np.isnan(f["z"].iloc[-1])
    assert spikes.detect_spikes(_weekly([0] * 8 + [5.0])).empty


def test_consecutive_spike_weeks_merged_and_start_values_used():
    vals = [10, 11, 9, 10, 11, 9, 10, 10, 40, 60, 10, 10]
    ev = spikes.detect_spikes(_weekly(vals))
    assert len(ev) == 1
    assert ev.loc[0, "n_weeks"] == 2
    assert abs(ev.loc[0, "start_multiplier"] - 40 / 9.833333) < 0.01


def test_multiplier_condition_blocks_small_bump():
    # 아주 평평한 시계열에서 살짝 오름: z는 크지만 배율 < 2 → 급증 아님
    vals = [10, 10.1, 9.9, 10, 10.1, 9.9, 10, 10, 13]
    assert spikes.detect_spikes(_weekly(vals)).empty


def test_exclude_right_after_publication():
    vals = [10, 11, 9, 10, 11, 9, 10, 10, 40]
    w = _weekly(vals)
    assert spikes.detect_spikes(w, pub_week=w.index[5]).empty
    assert len(spikes.detect_spikes(w, pub_week=w.index[0])) == 1


# ── event study ────────────────────────────────────────────
def test_event_study_pooled_ratio_keeps_zero_denominator_books():
    books = []
    for i in range(12):
        w = _weekly([0, 0, 0, 0, 2, 2, 2, 2] if i % 3 == 0 else [1, 1, 1, 1, 3, 3, 3, 3])
        books.append({"book_id": i, "group": "out200", "weekly": w,
                      "entry_week": w.index[-1] + pd.Timedelta(weeks=1)})
    for i in range(10):
        w = _weekly([1] * 8)
        books.append({"book_id": 100 + i, "group": "control", "weekly": w,
                      "entry_week": w.index[-1] + pd.Timedelta(weeks=1)})
    t = event_study.build_table(books)
    assert len(t) == 22
    s = event_study.summarize(t)
    assert abs(s.loc["out200", "zero_denominator_share"] - 4 / 12) < 1e-9
    assert event_study.go_check(t, Y=1.2)["verdict"] == "Go"


def test_event_study_too_few_books():
    w = _weekly([1] * 8)
    t = event_study.build_table([{"book_id": 1, "group": "out200", "weekly": w,
                                  "entry_week": w.index[-1] + pd.Timedelta(weeks=1)}])
    assert event_study.go_check(t, Y=1.2)["verdict"] == "판정 불가"
