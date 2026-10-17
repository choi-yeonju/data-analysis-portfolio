"""07 / 08 공통 정의.

07_baseline.ipynb 의 셀 정의를 그대로 옮긴 것이다 (함수 본문·상수 값 변경 금지).
정의가 07과 어긋나면 08 맨 위의 재현 assert 에서 걸린다.
07 → 이 모듈 import 로 바꾸는 건 08 완료 후 07 정리 단계에서 한다.
"""
import time
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import average_precision_score, precision_recall_curve

# ---- 상수 (07 셀 2, 38, 39, 41) ----
MASTER_PATH = "data/processed/master_features.parquet"
TRAIN_END = "2018-05-01"     # D-03: 학습 < TRAIN_END
TEST_END = "2018-09-01"      # 테스트 = [TRAIN_END, TEST_END)
STAGE1_NUM = ["distance_km_filled", "seller_avg_delay"]
STAGE1_BIN = ["dist_missing", "seller_avg_delay_is_fallback"]
STAGE1_CAT = ["category_grouped"]
STAGE2_NUM = ["price_sum", "freight_sum", "installments_max"]
NUM1, BIN1, CAT1 = STAGE1_NUM, STAGE1_BIN, STAGE1_CAT   # 07 의 num1, bin1, cat1
NUM2 = STAGE1_NUM + STAGE2_NUM                           # 07 의 num2
N_SPLITS = 5
GAP = 5000                   # D-20
N_EST = 300
CW_RANK = {None: 0, "balanced": 1}


# ---- 데이터 / 분할 ----
def load_master(path=MASTER_PATH):
    master = pd.read_parquet(path)
    assert len(master) == 96204
    return master


def get_masks(master):
    train_mask = master["purchase_ts"] < TRAIN_END
    test_mask = (master["purchase_ts"] >= TRAIN_END) & (master["purchase_ts"] < TEST_END)
    return train_mask, test_mask


def build_frames(master):
    """07 셀 38 + 40 + 42 와 동일: tr1, tr2, te1, te2 반환."""
    train_mask, test_mask = get_masks(master)
    tr1 = master[train_mask].sort_values(["purchase_ts", "order_id"]).reset_index(drop=True)
    tr2 = tr1[tr1["low"].notna()].reset_index(drop=True)
    assert tr1["purchase_ts"].max() < pd.Timestamp(TRAIN_END)
    te1 = master[test_mask]
    te2 = te1[te1["low"].notna()]
    return tr1, tr2, te1, te2


def make_splits(n):
    return list(TimeSeriesSplit(n_splits=N_SPLITS, gap=GAP).split(np.arange(n)))


# ---- 전처리 / 모델 ----
def make_preprocessor(num_cols, bin_cols, cat_cols):
    return ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("bin", "passthrough", bin_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
    ])


def logit_f(C, cw):
    return lambda: LogisticRegression(C=C, class_weight=cw, max_iter=1000, random_state=42)


def rf_f(d, l, cw):
    return lambda: RandomForestClassifier(n_estimators=N_EST, class_weight=cw, max_depth=d,
                                          min_samples_leaf=l, random_state=42, n_jobs=-1)


def build_grids():
    """07 셀 39, 41 의 그리드. (이름, make_clf, simp) 튜플 리스트 4개를 dict 로."""
    return {
        "grid1_logit": [(f"logit C={C}", logit_f(C, "balanced"), (C,)) for C in [0.01, 0.1, 1, 10]],
        "grid1_rf": [(f"rf depth={d} leaf={l}", rf_f(d, l, "balanced"), (d, -l))
                     for d in [4, 8, 12] for l in [50, 200]],
        "grid2_logit": [(f"logit C={C} cw={cw}", logit_f(C, cw), (CW_RANK[cw], C))
                        for C in [0.01, 0.1, 1, 10] for cw in [None, "balanced"]],
        "grid2_rf": [(f"rf depth={d} leaf={l} cw={cw}", rf_f(d, l, cw), (CW_RANK[cw], d, -l))
                     for d in [4, 8, 12] for l in [50, 200] for cw in [None, "balanced"]],
    }


def get_maker(grid, name):
    """선택된 설정 이름 → make_clf (07 의 mk1l/mk1r/mk2l/mk2r 에 해당)."""
    return [g[1] for g in grid if g[0] == name][0]


# ---- CV / 선택 / 임계값 (07 셀 39, 40) ----
def cv_run(df, ycol, num, bin_, cat, make_clf, splits):
    X = df[num + bin_ + cat]; y = df[ycol].astype(int).to_numpy()
    ratios, oof = [], np.full(len(df), np.nan)
    for a, b in splits:
        if len(np.unique(y[a])) < 2 or len(np.unique(y[b])) < 2:
            ratios.append(np.nan); continue
        pipe = Pipeline([("pre", make_preprocessor(num, bin_, cat)), ("clf", make_clf())])
        pipe.fit(X.iloc[a], y[a])
        p = pipe.predict_proba(X.iloc[b])[:, 1]
        ratios.append(average_precision_score(y[b], p) / y[b].mean())
        oof[b] = p
    return np.array(ratios), oof


def run_grid(df, ycol, num, bin_, cat, grid, splits):
    rows, oofs = [], {}
    for name, make_clf, simp in grid:
        t0 = time.time()
        r, oof = cv_run(df, ycol, num, bin_, cat, make_clf, splits)
        rows.append({"config": name, "mean_ratio": np.nanmean(r), "min_ratio": np.nanmin(r),
                     **{f"f{k+1}": v for k, v in enumerate(r)}, "simp": simp, "sec": round(time.time() - t0)})
        oofs[name] = oof
    return pd.DataFrame(rows), oofs


def pick(tbl, tol=0.005):
    """D-20: 최고 mean_ratio 와 tol 이내인 설정 중 가장 단순한(simp 작은) 설정"""
    cand = tbl[tbl["mean_ratio"] >= tbl["mean_ratio"].max() - tol]
    return cand.sort_values("simp").iloc[0]["config"]


def best_f1_threshold(y, p):
    pr, rc, th = precision_recall_curve(y, p)
    f1 = 2 * pr[:-1] * rc[:-1] / np.clip(pr[:-1] + rc[:-1], 1e-12, None)
    i = f1.argmax()
    return th[i], f1[i]


def lift_top(y, p, frac=0.10):
    k = max(int(len(y) * frac), 1); idx = np.argsort(-p)[:k]
    return y[idx].mean() / y.mean()


# ---- 적합 (08 신규: fit_pipeline. fit_prob 은 07 셀 46 과 동일 동작) ----
def fit_pipeline(make_clf, tr, ycol, num, bin_, cat):
    """적합된 Pipeline 반환 — 계수표·permutation importance 용 (08 신규 헬퍼)."""
    pipe = Pipeline([("pre", make_preprocessor(num, bin_, cat)), ("clf", make_clf())])
    pipe.fit(tr[num + bin_ + cat], tr[ycol].astype(int))
    return pipe


def fit_prob(make_clf, tr, ycol, num, bin_, cat, te):
    pipe = fit_pipeline(make_clf, tr, ycol, num, bin_, cat)
    return pipe.predict_proba(te[num + bin_ + cat])[:, 1]
