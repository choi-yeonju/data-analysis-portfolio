"""3단계 dev 라벨링 도구 (터미널). 실행은 olist 폴더, .venv 에서.

  python tools\\label_dev.py --ver v0                    # 첫 라벨링 (dev 1~50, 코드북 v0)
  python tools\\label_dev.py --pass relabel --ver v1     # 재라벨링 (첫 라벨은 화면에 안 보임)
  python tools\\label_dev.py --pass first --ver v1 --range 51 100
  python tools\\label_dev.py --summary                   # 건수·소요 시간·300/150건 결정식
  python tools\\label_dev.py --export                    # 커밋용 라벨 전용 파일(원문·번역·메모 없음)

입력 한 줄:  주유형 [부유형] 배송비태그 [메모]
  p1 f                 → 주 P1, 배송비 False
  p6a p3 t 배송비 비쌈  → 주 P6a, 부 P3, 배송비 True, 메모
  p6a+p3 u             → '+'로 붙여 써도 됨
  코드: P1 P2 P3 P4 P5 P6a P6b P9a P9b (대소문자·p 생략 가능: 1, 6a, 9a)
        P9는 p9a(판독 불가) / p9b(체계 밖)로만 입력하고 부 유형으로는 쓰지 않는다(코드북 v1 규칙 8·9)
  배송비태그: t / f / u  (True / False / U, 반드시 입력)
명령:  o 원문(포르투갈어) 보기 | b 이전 건 | g N N번(label_order)으로 이동 | k 건너뛰기
       p 일시정지(시간 제외) | q 저장 후 종료 | ? 도움말

안전장치
- dev 파일(stage3_label_dev.csv)만 읽고 쓴다. hold-out 원문 파일은 열지 않는다.
  (label_order 열이 없을 때만 manifest에서 review_id·label_order 두 열을 읽는다.)
- 화면에는 text_ko 만 먼저 보인다. 점수·가중치·층 정보는 보여 주지 않는다(앵커링 방지).
- 건마다 즉시 저장(임시 파일 → 교체). 시작 전 백업 1회.
- 재라벨은 별도 파일(stage3_relabel_dev.csv)에 쓰고 첫 라벨 열은 건드리지 않는다.
- 노트북 10은 다시 실행하지 않는다(이 도구와 무관).
- [패치] 파일이 엑셀 등에서 열려 있어 저장이 막히면 닫고 Enter로 재시도한다(저장 대기 시간은 소요 시간에서 뺀다).
- [패치] 라벨링을 시작할 때마다 backup/에 라벨·재라벨·시간 로그를 타임스탬프로 복사한다(각 20개까지 보관).
- [패치] 재라벨에서 다른 코드북 버전의 기존 라벨을 다시 달 때(예: v1 -> v2) 기존 재라벨 파일을
  stage3_relabel_dev.<버전>.csv 로 먼저 보관한다. --export 는 보관본도 함께 내보낸다.
"""
import argparse
import csv
import os
import shutil
import statistics
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DIR = Path("data/processed/stage3")
LABEL = DIR / "stage3_label_dev.csv"
RELABEL = DIR / "stage3_relabel_dev.csv"
TIMES = DIR / "stage3_label_times.csv"
MANIFEST = DIR / "stage3_sample_manifest.csv"
BACKUP = DIR / "stage3_label_dev.before_labeling.csv"
EXPORT = Path("outputs/labels/stage3_labels_dev.csv")
BACKUP_DIR = DIR / "backup"
KEEP_BACKUPS = 20

LABEL_COLS = ["label_main", "label_sub", "mentions_freight_cost", "codebook_ver", "memo"]
CODES = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b", "P9a", "P9b"]   # 코드북 v1: P9는 P9a(판독 불가)/P9b(체계 밖)
CODE_KEY = {c[1:].lower(): c for c in CODES}          # '1'->P1, '6a'->P6a
FREIGHT = {"t": "True", "true": "True", "f": "False", "false": "False", "u": "U"}
HOURS_BUDGET_MIN = 720                                 # §4: H = 12시간
N_ALL, N_RELABEL = 310, 100                            # §4 결정식의 건수


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def wr(df, p):
    tmp = Path(str(p) + ".tmp")
    while True:
        try:
            df.to_csv(tmp, index=False, encoding="utf-8-sig")
            os.replace(tmp, p)
            return
        except PermissionError:
            input(f"  ! {Path(p).name} 이(가) 엑셀 등에서 열려 있는 것 같음. 닫고 Enter를 누르면 다시 저장 > ")


def backup_all():
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for src in (LABEL, RELABEL, TIMES):
        if src.exists():
            shutil.copyfile(src, BACKUP_DIR / f"{src.stem}_{stamp}{src.suffix}")
            old = sorted(BACKUP_DIR.glob(f"{src.stem}_*{src.suffix}"))
            for f in old[:-KEEP_BACKUPS]:
                f.unlink()


def die(msg):
    print("중단:", msg)
    sys.exit(1)


def norm_code(s):
    s = s.strip().lower()
    if s.startswith("p"):
        s = s[1:]
    return CODE_KEY.get(s)


def parse(line):
    toks = line.split()
    if not toks:
        return None, "입력이 비었음"
    head = toks[0].split("+")
    if len(head) > 2:
        return None, "'+'는 한 번만 (주+부)"
    if any(h.strip().lower() in ("9", "p9") for h in head):
        return None, "P9는 p9a(판독 불가) 또는 p9b(체계 밖)로 입력"
    main = norm_code(head[0])
    if main is None:
        return None, f"주 유형 코드 오류 '{head[0]}' (가능: {', '.join(CODES)})"
    sub = ""
    if len(head) == 2:
        sub = norm_code(head[1])
        if sub is None:
            return None, f"부 유형 코드 오류 '{head[1]}'"
    i = 1
    if not sub and i < len(toks):
        c = norm_code(toks[i])
        if c is not None:
            sub, i = c, i + 1
    if sub == main:
        return None, "주 유형과 부 유형이 같음"
    if sub.startswith("P9"):
        return None, "P9 계열은 부 유형으로 쓰지 않음(코드북 v1 규칙 9). 다른 불만이 있으면 그쪽을 주 유형으로"
    if i >= len(toks):
        return None, "배송비 태그(t/f/u)가 필요함"
    fr = FREIGHT.get(toks[i].lower())
    if fr is None:
        return None, f"배송비 태그 오류 '{toks[i]}' (t / f / u)"
    return (main, sub, fr, " ".join(toks[i + 1:])), None


def load_label():
    if not LABEL.exists():
        die(f"{LABEL} 없음. olist 폴더에서 실행했는지 확인")
    lab = rd(LABEL)
    orig_cols = list(lab.columns)
    need = ["review_id", "text_pt", "text_ko"] + LABEL_COLS
    miss = [c for c in need if c not in lab.columns]
    if miss:
        die(f"{LABEL}에 없는 열: {miss}. 현재 열: {orig_cols}")
    if len(lab) != 204:
        die(f"dev 라벨 파일이 204행이 아님({len(lab)})")
    if lab["review_id"].duplicated().any():
        die("review_id 중복")
    if (lab["text_ko"].str.strip() == "").any():
        die("text_ko가 빈 행이 있음. tools\\merge_translations_dev.py 를 먼저 실행")
    if "label_order" in lab.columns:
        lab["_ord"] = lab["label_order"].astype(int)
    else:
        if not MANIFEST.exists():
            die("label_order 열도 manifest도 없음")
        man = pd.read_csv(MANIFEST, usecols=["review_id", "label_order"], dtype=str)
        mp = dict(zip(man["review_id"], man["label_order"]))
        lab["_ord"] = lab["review_id"].map(mp)
        if lab["_ord"].isna().any():
            die("manifest에서 label_order를 못 찾은 행이 있음")
        lab["_ord"] = lab["_ord"].astype(int)
    if lab["_ord"].duplicated().any():
        die("label_order 중복")
    return lab, orig_cols


def load_relabel(lab):
    if RELABEL.exists():
        rl = rd(RELABEL).set_index("review_id").reindex(lab["review_id"]).fillna("").reset_index()
        for c in LABEL_COLS:
            if c not in rl.columns:
                rl[c] = ""
    else:
        rl = pd.DataFrame({"review_id": lab["review_id"].values})
        for c in LABEL_COLS:
            rl[c] = ""
        wr(rl.assign(label_order=lab["_ord"].values)[["review_id", "label_order"] + LABEL_COLS], RELABEL)
    return rl


def append_time(row):
    while True:
        try:
            new = not TIMES.exists()
            with open(TIMES, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["saved_at", "pass", "ver", "label_order", "review_id", "seconds", "viewed_pt"])
                w.writerow(row)
            return
        except PermissionError:
            input(f"  ! {TIMES.name} 이(가) 열려 있는 것 같음. 닫고 Enter를 누르면 다시 기록 > ")


def read_times():
    if not TIMES.exists():
        return pd.DataFrame(columns=["saved_at", "pass", "ver", "label_order", "review_id", "seconds", "viewed_pt"])
    t = rd(TIMES)
    t["seconds"] = t["seconds"].astype(float)
    t["label_order"] = t["label_order"].astype(int)
    return t


def summary():
    t = read_times()
    if t.empty:
        print("시간 기록이 아직 없음")
        return
    t = t.drop_duplicates(["pass", "ver", "review_id"], keep="first")      # 수정·되돌리기 중복 제외
    print("패스·버전별 (건마다 첫 기록만 사용)")
    for (ps, ver), g in t.groupby(["pass", "ver"]):
        m = g["seconds"]
        print(f"  {ps}/{ver}: {len(g)}건, 평균 {m.mean() / 60:.2f}분/건, 중앙값 {m.median() / 60:.2f}분/건, 합 {m.sum() / 60:.1f}분")
    f = t[(t["pass"] == "first") & (t["ver"] == "v0") & (t["label_order"] <= 50)]
    r = t[(t["pass"] == "relabel") & (t["ver"] == "v1") & (t["label_order"] <= 50)]
    print("\n§4 결정식 (첫 50건: 첫 라벨 v0, v1 재라벨 기준)")
    if len(f) < 50 or len(r) < 50:
        print(f"  아직 계산 불가: 첫 라벨 v0 {len(f)}/50건, v1 재라벨 {len(r)}/50건")
        return
    a, b = f["seconds"].mean() / 60, r["seconds"].mean() / 60
    est = a * N_ALL + b * N_RELABEL
    print(f"  {a:.2f}분 × {N_ALL} + {b:.2f}분 × {N_RELABEL} = {est:.0f}분 (기준 {HOURS_BUDGET_MIN}분)")
    print("  →", "150건 축소 (154 + 100회)" if est > HOURS_BUDGET_MIN else "300건 유지 (310 + 100회)")
    print("  결정은 규칙 문서 '커밋 후 기록' 구간에 날짜와 함께 직접 덧붙인다.")


def export(with_memo):
    lab, _ = load_label()
    rl = load_relabel(lab)
    parts = []
    cols = ["review_id", "label_order", "pass", "label_main", "label_sub", "mentions_freight_cost", "codebook_ver"]
    if with_memo:
        cols.append("memo")
    sources = [("first", lab), ("relabel", rl)]
    for f in sorted(DIR.glob("stage3_relabel_dev.v*.csv")):          # 다른 버전으로 덮어쓰기 전 보관본
        ver = f.name[len("stage3_relabel_dev."):-len(".csv")]
        arch = rd(f).set_index("review_id").reindex(lab["review_id"]).fillna("").reset_index()
        for c in LABEL_COLS:
            if c not in arch.columns:
                arch[c] = ""
        same = (arch[["label_main", "label_sub", "mentions_freight_cost", "codebook_ver"]].values
                == rl[["label_main", "label_sub", "mentions_freight_cost", "codebook_ver"]].values).all(axis=1)
        arch.loc[same, "label_main"] = ""                       # 현재 재라벨과 같은 행은 중복이라 제외
        sources.append((f"relabel_보관_{ver}", arch))
    for name, df in sources:
        d = pd.DataFrame({"review_id": lab["review_id"].values, "label_order": lab["_ord"].values, "pass": name})
        for c in LABEL_COLS:
            d[c] = df[c].values
        parts.append(d[d["label_main"] != ""])
    out = pd.concat(parts, ignore_index=True).sort_values(["pass", "label_order"])[cols]
    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(EXPORT, index=False, encoding="utf-8-sig")
    print(f"내보냄: {EXPORT} ({len(out)}행: " + ", ".join(f"{k} {v}" for k, v in out['pass'].value_counts().items()) + ")")
    print("원문·번역은 들어 있지 않음." + ("" if with_memo else " 메모도 제외(원문 조각이 섞일 수 있어서)."))
    print("커밋 전에 git status 로 이 파일만 새로 올라가는지, data/ 아래가 없는지 확인하세요.")


def wrap(s):
    return "\n".join(textwrap.fill(p, 76) if p.strip() else "" for p in s.splitlines()) or s


def main():
    ap = argparse.ArgumentParser(description="3단계 dev 라벨링 도구")
    ap.add_argument("--pass", dest="ps", choices=["first", "relabel"], default="first")
    ap.add_argument("--ver", help="코드북 버전 (예: v0, v1). 라벨링할 때 필수")
    ap.add_argument("--range", nargs=2, type=int, default=[1, 50], metavar=("LO", "HI"), help="label_order 범위(기본 1 50)")
    ap.add_argument("--redo", action="store_true", help="이미 라벨 있는 건부터 다시 시작")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--with-memo", action="store_true", help="--export에 메모 열 포함(기본은 제외)")
    a = ap.parse_args()

    if a.summary:
        return summary()
    if a.export:
        return export(a.with_memo)
    if not a.ver:
        die("--ver 가 필요함 (예: --ver v0). 코드북 버전을 모르는 채로 라벨을 달지 않기 위해서")

    lab, orig_cols = load_label()
    backup_all()
    lo, hi = a.range
    if a.ps == "first":
        target, path = lab, LABEL
        if not BACKUP.exists():
            shutil.copyfile(LABEL, BACKUP)
    else:
        target, path = load_relabel(lab), RELABEL
    order = lab.sort_values("_ord").index.tolist()
    rows = [i for i in order if lo <= lab.at[i, "_ord"] <= hi]
    if not rows:
        die(f"범위 {lo}~{hi}에 해당하는 행이 없음")

    old_vers = []
    if a.ps == "relabel":
        old_vers = sorted({target.at[i, "codebook_ver"] for i in rows
                           if target.at[i, "label_main"] != "" and target.at[i, "codebook_ver"] not in ("", a.ver)})
        for ov in old_vers:
            cur = rd(RELABEL)
            cur = cur[(cur["codebook_ver"] == ov) & (cur["label_main"] != "")]
            arch = DIR / f"stage3_relabel_dev.{ov}.csv"
            if arch.exists():                                   # 보관본 갱신: 같은 건은 최신 값으로, 새 건은 추가
                prev = rd(arch)
                prev = prev[~prev["review_id"].isin(set(cur["review_id"]))]
                cur = pd.concat([prev[cur.columns], cur], ignore_index=True)
            wr(cur, arch)
            print(f"알림: 이 범위에 {ov}로 단 기존 재라벨이 있음 -> {arch.name} 에 {len(cur)}건 보관(갱신)함 "
                  f"(kappa 증거용, 덮어쓰지 않음).")

    if a.ps == "relabel" and any(lab.at[i, "_ord"] > 50 for i in rows):
        t = read_times()
        t = t[(t["pass"] == "first") & (t["label_order"].isin([lab.at[i, "_ord"] for i in rows]))]
        if not t.empty:
            last = pd.to_datetime(t["saved_at"]).max()
            days = (datetime.now() - last.to_pydatetime()).total_seconds() / 86400
            if days < 3:
                print(f"주의: 이 범위의 마지막 첫 라벨이 {days:.1f}일 전입니다. 규칙은 3~4일 뒤 재라벨링입니다.")
                if input("그래도 진행할까요? (y/N) ").strip().lower() != "y":
                    return

    def done(i):
        return target.at[i, "label_main"] != ""

    def next_pos(start):
        for p in list(range(start, len(rows))) + list(range(0, start)):
            if a.redo and p < start:
                continue
            if a.redo and p >= start:
                return p
            if not done(rows[p]):
                return p
        return None

    pos = next_pos(0) if not a.redo else 0
    if pos is None:
        print(f"범위 {lo}~{hi}는 이 패스({a.ps})에서 이미 모두 라벨링됨. --summary 로 시간을 확인하세요.")
        if old_vers:
            print(f"다른 버전({', '.join(old_vers)})으로 이미 재라벨됨. {a.ver}로 다시 달려면 --redo 를 붙이세요(기존본은 보관됨).")
        return
    print(f"패스 {a.ps} / 코드북 {a.ver} / 범위 {lo}~{hi} ({len(rows)}건). ? 로 도움말, q 로 종료.")

    def show(p):
        i = rows[p]
        n_done = sum(done(r) for r in rows)
        print("\n" + "=" * 72)
        print(f"[#{lab.at[i, '_ord']}  {a.ps}/{a.ver}  완료 {n_done}/{len(rows)}]")
        print(wrap(lab.at[i, "text_ko"]))
        if done(i):
            print(f"(이 패스의 기존 라벨: {target.at[i, 'label_main']}"
                  f"{'+' + target.at[i, 'label_sub'] if target.at[i, 'label_sub'] else ''}"
                  f" / 배송비 {target.at[i, 'mentions_freight_cost']} / {target.at[i, 'codebook_ver']})")

    try:
        while pos is not None:
            i = rows[pos]
            show(pos)
            start, paused, viewed = time.monotonic(), 0.0, False
            while True:
                try:
                    line = input("> ").strip()
                except EOFError:
                    print("\n입력 종료. 저장된 라벨은 그대로 유지됨.")
                    return
                cmd = line.split()[0].lower() if line else ""
                if cmd in ("?", "h"):
                    print(__doc__.split("안전장치")[0])
                elif cmd == "o":
                    print("--- 원문 ---\n" + wrap(lab.at[i, "text_pt"]) + "\n------------")
                    viewed = True
                elif cmd == "p":
                    t0 = time.monotonic()
                    input("일시정지 중. 재개하려면 Enter ")
                    paused += time.monotonic() - t0
                elif cmd == "q":
                    print("종료. 지금까지 저장됨.")
                    return
                elif cmd == "k":
                    pos = pos + 1 if pos + 1 < len(rows) else pos
                    break
                elif cmd == "b":
                    pos = max(pos - 1, 0)
                    break
                elif cmd == "g":
                    try:
                        n = int(line.split()[1])
                        pos = next(p for p, r in enumerate(rows) if lab.at[r, "_ord"] == n)
                        break
                    except (IndexError, ValueError, StopIteration):
                        print(f"사용법: g N  (범위 {lo}~{hi} 안의 label_order)")
                else:
                    res, err = parse(line)
                    if err:
                        print("  ✗", err)
                        continue
                    main_, sub_, fr_, memo_ = res
                    target.at[i, "label_main"], target.at[i, "label_sub"] = main_, sub_
                    target.at[i, "mentions_freight_cost"], target.at[i, "codebook_ver"] = fr_, a.ver
                    target.at[i, "memo"] = memo_
                    secs = time.monotonic() - start - paused          # 저장 대기(엑셀 닫기 등)는 시간에 넣지 않음
                    if a.ps == "first":
                        wr(target[orig_cols], path)
                    else:
                        wr(target.assign(label_order=lab["_ord"].values)[["review_id", "label_order"] + LABEL_COLS], path)
                    append_time([datetime.now().isoformat(timespec="seconds"), a.ps, a.ver,
                                 int(lab.at[i, "_ord"]), lab.at[i, "review_id"], f"{secs:.1f}", int(viewed)])
                    print(f"  ✓ 저장 ({secs:.0f}초)")
                    nxt = next_pos(pos + 1) if pos + 1 < len(rows) or not a.redo else None
                    if a.redo:
                        nxt = pos + 1 if pos + 1 < len(rows) else None
                    pos = nxt
                    break
    except KeyboardInterrupt:
        print("\n중단. 저장된 라벨은 그대로 유지됨.")
        return
    print("\n범위 끝. --summary 로 소요 시간을, --export 로 커밋용 라벨 파일을 확인하세요.")


if __name__ == "__main__":
    main()
