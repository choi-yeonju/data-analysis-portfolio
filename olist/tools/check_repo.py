"""프로젝트 정합성 점검 (프로젝트 루트 olist/ 에서 실행: python tools/check_repo.py)
문서(docs/*.md) ↔ 노트북 ↔ 결과 표(outputs/tables) 사이의 기계적으로 확인 가능한 오류를 찾는다.

검사 항목
  A 문서가 인용한 노트북·코드 파일이 실제로 있는가
  A2 노트북 안(마크다운·주석)이 인용한 노트북 파일명이 실제로 있는가
  A3 코드(.py: src/, tools/)가 인용한 노트북 파일명이 실제로 있는가
  B 남으면 안 되는 표기(날짜 placeholder, 옛 버전, TODO)
  B2 log.md의 Day 제목에 날짜가 있는가
  C 노트북 실행 상태(미실행 셀, 실행 번호 불연속, 에러 출력)
  D decisions.md의 D-번호 중복·인용
  E results.csv ↔ 문서
  F 숫자 출처 점검(문서 속 숫자가 노트북·표에 없으면 목록으로. 걸린다고 모두 오류는 아님)
  G 재현성: 무작위 요소를 쓰는데 시드가 없는 노트북
  H 핵심 숫자: tools/key_numbers.json에 적은 숫자가 지정한 노트북에 실제로 있는가

사용 예
  python tools/check_repo.py                        # 기본: F는 Day 6 이후 변경분만(노이즈 적음)
  python tools/check_repo.py --scope all            # F를 문서 전체로
  python tools/check_repo.py --skip-nb 진행중.ipynb  # 노트북 임시 제외(실행 순서·미실행 셀만 건너뜀, 에러 출력은 계속 검사)
  python tools/check_repo.py --skip B2               # 검사 끄기. 제외한 항목은 결과 맨 위에 '제외됨'으로 표시
  (옛 사용법 --skip 파일.ipynb 도 --skip-nb 로 처리한다)
"""
import argparse, glob, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Code Runner·PowerShell에서 한글 깨짐 방지
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=".")
ap.add_argument("--scope", choices=["all", "day6"], default="day6", help="F 검사 범위 (기본 day6: Day 6 이후 변경분, all: 문서 전체)")
ap.add_argument("--all", action="store_true", help="(호환용) --scope all과 같음")
ap.add_argument("--skip-nb", nargs="*", default=[], help="검사에서 뺄 노트북 파일명")
ap.add_argument("--skip-ref", nargs="*", default=[], help="[A]에서 무시할 인용 노트북 이름")
ap.add_argument("--skip", nargs="*", default=[], help="끌 검사 문자 (예: B C)")
args = ap.parse_args()
_moved = [s for s in args.skip if s.lower().endswith(".ipynb")]   # 옛 사용법 호환
args.skip = [s for s in args.skip if s not in _moved]
args.skip_nb = list(args.skip_nb) + _moved

ROOT = args.root
SKIP_CHECKS = {s.upper() for s in args.skip}
on = lambda k: k not in SKIP_CHECKS
DOCS = ["decisions", "log", "data_dictionary", "agenda", "agenda_onepager", "final_report"]   # [2026-10-30] final_report 추가   # stage3_rules.md는 원본 CSV 기준 수치라 숫자 출처 점검(F)에서 제외
ALLOW_F = {"−0.50"}            # F 오탐 허용: 강사님 코멘트 인용 숫자(노트북 출력이 아님). 출처를 직접 확인한 것만, 이유를 적어서 추가
HIST_OK = re.compile(r"04_eda_day4")   # A2·A3 예외: 이력 설명용 옛 노트북 이름 (추가할 때 이유를 주석으로)
problems, warns, skipped = [], [], []

def rd(p): return open(p, encoding="utf-8").read()
def nb_cells(p): return json.load(open(p, encoding="utf-8"))["cells"]

docs = {d: rd(f"{ROOT}/docs/{d}.md") for d in DOCS if os.path.exists(f"{ROOT}/docs/{d}.md")}
all_nb = sorted(glob.glob(f"{ROOT}/notebooks/*.ipynb"))
notebooks = [p for p in all_nb if os.path.basename(p) not in set(args.skip_nb)]
nb_names = {os.path.basename(p) for p in all_nb}          # [A]는 실제 존재 여부라 제외 전 목록 기준

if args.skip_nb: skipped.append(f"노트북 제외: {', '.join(args.skip_nb)}")
if args.skip_ref: skipped.append(f"[A] 인용 무시: {', '.join(args.skip_ref)}")
if SKIP_CHECKS: skipped.append(f"검사 끔: {', '.join(sorted(SKIP_CHECKS))}")
if _moved: skipped.append(f"--skip에 노트북 이름이 와서 --skip-nb로 처리함: {', '.join(_moved)}")
for n in args.skip_nb:
    if n not in nb_names: warns.append(f"[설정] --skip-nb {n!r}: notebooks/에 그런 파일이 없음 (오타 확인)")

def nb_text(p):
    """노트북의 코드·마크다운 소스와 출력 텍스트를 한 문자열로"""
    t = ""
    for c in nb_cells(p):
        t += "\n" + "".join(c["source"])
        for o in c.get("outputs", []):
            t += "\n" + ("".join(o.get("text", [])) if o.get("output_type") == "stream"
                         else "".join(o.get("data", {}).get("text/plain", [])))
    return t

# ---------- A ----------
if on("A"):
    for d, s in docs.items():
        for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", s))):
            if m in args.skip_ref: continue
            if m not in nb_names: problems.append(f"[A] {d}.md가 인용한 {m} 없음 (notebooks/ 파일명 확인)")
        if "src/common.py" in s and not os.path.exists(f"{ROOT}/src/common.py"):
            problems.append(f"[A] {d}.md가 src/common.py를 인용하는데 파일 없음")
    # 파일명에 공백·(1) 같은 복사 흔적이 있으면 미리 알려줌
    for n in sorted(nb_names):
        if re.search(r"\s|\(\d+\)", n): warns.append(f"[A] 노트북 파일명에 공백/복사 흔적: {n!r}")

# ---------- A2: 노트북 안(마크다운·주석)이 인용한 노트북 파일명 ----------
if on("A2"):
    for p in notebooks:
        for i, c in enumerate(nb_cells(p)):
            for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", "".join(c["source"])))):
                if m in nb_names or m in args.skip_ref or HIST_OK.search(m): continue
                problems.append(f"[A2] {os.path.basename(p)} 셀 {i}가 인용한 {m} 없음 (낡은 파일명?)")

# ---------- A3: 코드(.py)가 인용한 노트북 파일명 (src/, tools/) ----------
if on("A3"):
    _me = os.path.abspath(__file__)
    for py in sorted(glob.glob(f"{ROOT}/src/*.py") + glob.glob(f"{ROOT}/tools/*.py")):
        if os.path.abspath(py) == _me: continue          # 이 스크립트의 안내 문구는 제외
        for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", rd(py)))):
            if m in nb_names or m in args.skip_ref or HIST_OK.search(m): continue
            problems.append(f"[A3] {os.path.basename(py)}가 인용한 {m} 없음 (낡은 파일명?)")

# ---------- B ----------
if on("B"):
    for d, s in docs.items():
        for pat, why in [(r"\(날짜 기입\)", "날짜 placeholder"), (r"_v\d+\.ipynb|\bv1[0-9]\b", "옛 버전 표기"),
                         (r"TODO|FIXME|XXX", "미완 표시")]:
            for m in re.finditer(pat, s):
                ln = s[:m.start()].count("\n") + 1
                problems.append(f"[B] {d}.md L{ln}: {why} '{m.group(0)}'")

# ---------- B2: log.md의 Day 제목에 날짜 ----------
if on("B2") and "log" in docs:
    for m in re.finditer(r"^## (Day \d+[^\n]*)$", docs["log"], flags=re.M):
        if not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|\d{2}-\d{2}", m.group(1)):
            problems.append(f"[B2] log.md '{m.group(1)[:40]}' 제목에 날짜 없음")

# ---------- C ----------
if on("C"):
    for p in notebooks:
        cells = nb_cells(p); name = os.path.basename(p)
        code = [c for c in cells if c["cell_type"] == "code" and "".join(c["source"]).strip()]
        ec = [c.get("execution_count") for c in code]
        if any(e is None for e in ec): problems.append(f"[C] {name}: 실행 안 된 코드 셀 {sum(e is None for e in ec)}개")
        elif ec != list(range(1, len(ec) + 1)):
            problems.append(f"[C] {name}: 실행 번호가 1부터 연속이 아님 (Restart & Run All 다시) {ec[:5]}...")
        for i, c in enumerate(cells):
            for o in c.get("outputs", []):
                if o.get("output_type") == "error": problems.append(f"[C] {name} 셀 {i}: 에러 출력 {o.get('ename')}")
                txt = "".join(o.get("text", [])) if o.get("output_type") == "stream" else ""
                if txt.count("findfont") > 3: warns.append(f"[C] {name} 셀 {i}: 폰트 경고 출력 {txt.count('findfont')}줄")
                if len(txt) > 20000: warns.append(f"[C] {name} 셀 {i}: 출력이 너무 김({len(txt)}자)")
        size = os.path.getsize(p) / 1e6
        if size > 3: warns.append(f"[C] {name}: 파일 {size:.1f}MB (출력·이미지 확인)")

    for p in all_nb:   # --skip-nb 로 뺀 노트북도 에러 출력은 계속 검사
        name = os.path.basename(p)
        if name in set(args.skip_nb):
            for i, c in enumerate(nb_cells(p)):
                for o in c.get("outputs", []):
                    if o.get("output_type") == "error":
                        problems.append(f"[C] {name} 셀 {i}: 에러 출력 {o.get('ename')} (제외한 노트북이지만 에러는 검사)")

# ---------- D ----------
if on("D") and "decisions" in docs:
    heads = re.findall(r"^#{2,4} (D-\d+[a-z]?)\b", docs["decisions"], flags=re.M)
    dup = {h for h in heads if heads.count(h) > 1}
    if dup: problems.append(f"[D] decisions.md에 같은 D-번호 제목이 중복: {sorted(dup)}")
    refs = set(re.findall(r"\bD-\d+[a-z]?\b", "\n".join(docs.values())))
    missing = sorted(r for r in refs if r not in set(heads) and not any(h.startswith(r) for h in heads))
    if missing: warns.append(f"[D] 제목은 없는데 문서에서 인용되는 번호(후속·하위 번호일 수 있음): {missing}")

# ---------- E ----------
if on("E"):
    rp = f"{ROOT}/outputs/tables/results.csv"
    if os.path.exists(rp):
        import pandas as pd
        r = pd.read_csv(rp); text = "\n".join(docs.values())
        need = ["단계", "모델", "PR-AUC/기저율", "PR-AUC", "top10_lift", "top5_lift"]
        lack = [c for c in need if c not in r.columns]
        if lack: problems.append(f"[E] results.csv에 필요한 컬럼 없음: {lack} (현재 {list(r.columns)})")
        else:
            for _, row in r.iterrows():
                for col, fmt in [("PR-AUC/기저율", "{:.3f}"), ("PR-AUC", "{:.4f}")]:
                    v = fmt.format(row[col])
                    if v not in text and v.rstrip("0") not in text:
                        warns.append(f"[E] results.csv {row['단계']} {row['모델']} {col}={v} 가 문서에 없음")
                for k in ("top10_lift", "top5_lift"):
                    v = f"{row[k]:.2f}"
                    if v not in text: warns.append(f"[E] results.csv {row['단계']} {row['모델']} {k}={v} 가 문서에 없음")
    else:
        warns.append("[E] outputs/tables/results.csv 없음 (08 5-1 셀을 실행했는지)")

# ---------- F ----------
if on("F"):
    NUM = re.compile(r"(?<![\w.])[−-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?p?|(?<![\w.])[−-]?\d+\.\d+%?p?|(?<![\w.])\d{3,}%?")
    def numbers(s): return [(m.start(), m.group(0)) for m in NUM.finditer(s)]
    def to_float(t):
        pct = "%" in t
        v = float(t.replace(",", "").replace("%p", "").replace("%", "").replace("−", "-"))
        return v, pct, (len(t.replace("%p", "").replace("%", "").split(".")[1]) if "." in t else 0)
    src_text = ""
    for p in notebooks: src_text += "\n" + nb_text(p)
    for p in glob.glob(f"{ROOT}/outputs/tables/*.csv"): src_text += "\n" + rd(p)
    # [2026-10-30 추가] 3단계 숫자는 도구 스크립트의 assert·기대값과 도구 실행 기록에 있으므로 함께 찾는다
    for p in glob.glob(f"{ROOT}/tools/*.py"): src_text += "\n" + rd(p)
    for p in glob.glob(f"{ROOT}/docs/*_log.txt") + glob.glob(f"{ROOT}/outputs/logs/*.txt"): src_text += "\n" + rd(p)
    pool = set()
    for _, t in numbers(src_text.replace("−", "-")):
        try: pool.add(float(t.replace(",", "").replace("%", "")))
        except: pass
    for m in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?", src_text):
        try: pool.add(float(m.group(0)))
        except: pass
    def found(v, pct, d):
        cands = {v} | ({v / 100} if pct else set()) | ({v * 100} if not pct and abs(v) < 1 else set())
        for f in pool:
            for c in cands:
                if abs(round(f, d) - c) < 1e-9 or abs(round(f * 100, d) - c) < 1e-9 and pct: return True
                if abs(round(f, d + 2) - round(c, d + 2)) < 1e-9 and pct: return True
        return False
    ALL = args.scope == "all" or args.all
    def day6_scope(d, s):
        if ALL or d == "agenda": return s
        if d == "log": return s[s.index("## Day 6"):] if "## Day 6" in s else ""
        if d == "data_dictionary": return s[s.index("## 07·08 산출물"):] if "## 07·08 산출물" in s else ""
        if d == "decisions":
            parts = []
            if "### D-20" in s: parts.append(s[s.index("### D-20"):])
            for key in ["한계 3(Day 6", "후속3(Day 6", "Day 6 모델 기준 재확인", "Day 6 확인:"]:
                for line in s.split("\n"):
                    if line.lstrip().startswith("- " + key) or key in line[:30]: parts.append(line)
            return "\n".join(parts)
        return s
    unmatched = {}
    for d, s in docs.items():
        s = day6_scope(d, s)
        for ln, line in enumerate(s.split("\n"), 1):
            if re.search(r"노트북 밖|원본 CSV|근사", line): continue
            clean = re.sub(r"D-\d+[a-z]?|\b\d+-\d+\b|20\d\d-\d\d(?:-\d\d)?|\b\d{2}_[A-Za-z0-9_]+|\bv\d+\b|\d+/\d+(?:~\d+)?", " ", line)
            for _, t in numbers(clean):
                if t in ALLOW_F: continue
                try: v, pct, dec = to_float(t)
                except: continue
                if 1900 <= abs(v) <= 2100 and not pct and dec == 0: continue
                if not found(v, pct, dec): unmatched.setdefault(d, []).append((ln, t, line.strip()[:90]))
    for d, lst in unmatched.items():
        warns.append(f"[F] {d}.md({'전체' if ALL else 'Day 6 범위'}): 노트북·표에서 못 찾은 숫자 {len(lst)}개 (출처 셀과 직접 대조)")
        seen = set()
        for ln, t, ctx in lst:
            if (ln, t) in seen: continue
            seen.add((ln, t)); warns.append(f"      L{ln} {t}  …{ctx}")

# ---------- G 재현성: 무작위 요소 + 시드 없음 ----------
if on("G"):
    RAND = re.compile(r"\.sample\(|train_test_split|shuffle|np\.random|\brandom\.|RandomForest|GradientBoosting|"
                      r"XGB|LGBM|USING\s+SAMPLE|ORDER\s+BY\s+random\(\)|KFold", re.I)
    SEED = re.compile(r"random_state|\bseed\b|default_rng\(\s*\d|setseed|REPEATABLE|SEED\s*=", re.I)
    for p in notebooks:
        code = "\n".join("".join(c["source"]) for c in nb_cells(p) if c["cell_type"] == "code")
        hits = sorted({m.group(0).lower() for m in RAND.finditer(code)})
        if hits and not SEED.search(code):
            warns.append(f"[G] {os.path.basename(p)}: 무작위 요소 {hits[:4]}가 있는데 시드(random_state/seed)가 안 보임 → 재실행 시 숫자가 바뀔 수 있음")

# ---------- H 핵심 숫자 ----------
if on("H"):
    kp = f"{ROOT}/tools/key_numbers.json"
    if os.path.exists(kp):
        try: keys = json.load(open(kp, encoding="utf-8"))
        except Exception as e: keys = []; problems.append(f"[H] key_numbers.json 읽기 실패: {e}")
        cache = {}
        for k in keys:
            nb = k["notebook"]; val = str(k["value"]).replace(",", "")
            if nb in args.skip_nb: warns.append(f"[H] '{k['label']}' 건너뜀 ({nb} 제외됨)"); continue
            path = f"{ROOT}/notebooks/{nb}"
            if not os.path.exists(path): problems.append(f"[H] '{k['label']}': {nb} 없음"); continue
            if nb not in cache: cache[nb] = nb_text(path).replace(",", "")
            if not re.search(rf"(?<![\d.]){re.escape(val)}(?![\d])", cache[nb]):
                problems.append(f"[H] '{k['label']}' = {k['value']} 가 {nb}의 소스·출력에 없음 (숫자가 바뀌었거나 셀을 다시 돌렸는지)")
    else:
        warns.append("[H] tools/key_numbers.json 없음 (핵심 숫자 검사 생략)")

# ---------- 출력 ----------
os.makedirs(f"{ROOT}/tools", exist_ok=True)
head = [f"제외됨: {x}" for x in skipped]
open(f"{ROOT}/tools/check_report.txt", "w", encoding="utf-8").write("\n".join(head + problems + [""] + warns))
if skipped:
    print("!! 아래 항목은 제외하고 실행됨 (통과해도 전체 통과가 아님)")
    for x in skipped: print("  -", x)
    print()
print("=== 오류 후보 (고쳐야 함) ===" if problems else "=== 오류 후보 없음 ===")
for x in problems: print(" ", x)
print("\n=== 확인 필요 (경고) ===" if warns else "\n=== 경고 없음 ===")
print("  (참고) F는 소수 1~2자리 숫자가 우연히 일치해 통과할 수 있어 통과가 정확하다는 보증은 아님. 큰 숫자·3자리 소수 위주로 해석.")
for x in warns[:200]: print(" ", x)
if len(warns) > 200: print(f"  ... 외 {len(warns)-200}줄 (전체는 tools/check_report.txt)")
sys.exit(1 if problems else 0)
