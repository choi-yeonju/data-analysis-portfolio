"""프로젝트 정합성 점검 (프로젝트 루트 olist/ 에서 실행: python tools/check_repo.py  /  전체 문서 점검: --all)
문서(docs/*.md) ↔ 노트북 ↔ 결과 표(outputs/tables) 사이의 기계적으로 확인 가능한 오류를 찾는다.
'숫자 출처 점검'은 문서 속 숫자가 노트북 출력·마크다운·표 어디에도 없을 때 알려주는 것이라, 걸린다고 모두 오류는 아니다(직접 확인용 목록).
"""
import json, re, sys, glob, os
import pandas as pd

ROOT = "."
DOCS = ["decisions", "log", "data_dictionary", "agenda", "agenda_onepager"]   # stage3_rules.md 는 원본 CSV 기준 수치라 숫자 출처 점검(F)에서 제외
problems, warns = [], []
# 진행 중이라 실행 상태 검사(C)에서 빼고 싶은 노트북: 코드에 적거나 --skip <노트북 파일명> 로 지정 (예: 3단계 작업 중인 노트북)
SKIP_NB = set()
for i, a in enumerate(sys.argv):
    if a == "--skip" and i + 1 < len(sys.argv): SKIP_NB.add(os.path.basename(sys.argv[i + 1]))
# 숫자 출처 점검(F)에서 알려진 오탐(예: 강사님 코멘트 인용 숫자)을 건너뛸 목록
ALLOW_F = {"−0.50"}

def rd(p): return open(p, encoding="utf-8").read()
def nb_cells(p): return json.load(open(p, encoding="utf-8"))["cells"]

docs = {d: rd(f"{ROOT}/docs/{d}.md") for d in DOCS if os.path.exists(f"{ROOT}/docs/{d}.md")}
notebooks = sorted(glob.glob(f"{ROOT}/notebooks/*.ipynb"))
nb_names = {os.path.basename(p) for p in notebooks}

# ---------- A. 문서가 인용하는 노트북·코드 파일이 실제로 있는가 ----------
for d, s in docs.items():
    for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", s))):
        if m not in nb_names: problems.append(f"[A] {d}.md가 인용한 {m} 없음 (notebooks/ 파일명 확인)")
    if "src/common.py" in s and not os.path.exists(f"{ROOT}/src/common.py"): problems.append(f"[A] {d}.md가 src/common.py를 인용하는데 파일 없음")


# ---------- A2. 노트북 안(마크다운·주석)이 인용하는 노트북 파일명이 실제로 있는가 ----------
HIST_OK = re.compile(r"04_eda_day4")        # 이력 설명용 옛 이름은 예외 (필요하면 추가)
for p in notebooks:
    for i, c in enumerate(nb_cells(p)):
        for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", "".join(c["source"])))):
            if m not in nb_names and not HIST_OK.search(m):
                problems.append(f"[A2] {os.path.basename(p)} 셀 {i}가 인용한 {m} 없음 (낡은 파일명?)")

# ---------- A3. 코드(.py)가 인용하는 노트북 파일명이 실제로 있는가 (src/, tools/) ----------
for py in sorted(glob.glob(f"{ROOT}/src/*.py") + glob.glob(f"{ROOT}/tools/*.py")):
    for m in sorted(set(re.findall(r"\b\d{2}_[A-Za-z0-9_]+\.ipynb", rd(py)))):
        if m not in nb_names and not HIST_OK.search(m):
            problems.append(f"[A3] {os.path.basename(py)}가 인용한 {m} 없음 (낡은 파일명?)")

# ---------- B. 남으면 안 되는 표기 ----------
for d, s in docs.items():
    for pat, why in [(r"\(날짜 기입\)", "날짜 placeholder"), (r"_v\d+\.ipynb|\bv1[0-9]\b", "옛 버전 표기"),
                     (r"TODO|FIXME|XXX", "미완 표시")]:
        for m in re.finditer(pat, s):
            ln = s[:m.start()].count("\n") + 1
            problems.append(f"[B] {d}.md L{ln}: {why} '{m.group(0)}'")


if "log" in docs:
    for m in re.finditer(r"^## (Day \d+[^\n]*)$", docs["log"], flags=re.M):
        if not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|\d{2}-\d{2}", m.group(1)):
            problems.append(f"[B2] log.md '{m.group(1)[:40]}' 제목에 날짜 없음")

# ---------- C. 노트북 실행 상태 ----------
for p in notebooks:
    cells = nb_cells(p); name = os.path.basename(p)
    if name in SKIP_NB:
        warns.append(f"[C] {name}: --skip 로 실행 순서·미실행 셀 검사만 제외 (에러 출력은 계속 검사)")
        for i, c in enumerate(cells):
            for o in c.get("outputs", []):
                if o.get("output_type") == "error": problems.append(f"[C] {name} 셀 {i}: 에러 출력 {o.get('ename')}")
        continue
    code = [c for c in cells if c["cell_type"] == "code" and "".join(c["source"]).strip()]
    ec = [c.get("execution_count") for c in code]
    if any(e is None for e in ec): problems.append(f"[C] {name}: 실행 안 된 코드 셀 {sum(e is None for e in ec)}개")
    else:
        if ec != list(range(1, len(ec) + 1)): problems.append(f"[C] {name}: 실행 번호가 1부터 연속이 아님 (Restart & Run All 다시) {ec[:5]}...")
    for i, c in enumerate(cells):
        for o in c.get("outputs", []):
            if o.get("output_type") == "error": problems.append(f"[C] {name} 셀 {i}: 에러 출력 {o.get('ename')}")
            txt = "".join(o.get("text", [])) if o.get("output_type") == "stream" else ""
            if txt.count("findfont") > 3: warns.append(f"[C] {name} 셀 {i}: 폰트 경고 출력 {txt.count('findfont')}줄")
            if len(txt) > 20000: warns.append(f"[C] {name} 셀 {i}: 출력이 너무 김({len(txt)}자)")
    size = os.path.getsize(p) / 1e6
    if size > 3: warns.append(f"[C] {name}: 파일 {size:.1f}MB (출력·이미지 확인)")

# ---------- D. decisions의 D-번호 ----------
if "decisions" in docs:
    heads = re.findall(r"^#{2,4} (D-\d+[a-z]?)\b", docs["decisions"], flags=re.M)
    dup = {h for h in heads if heads.count(h) > 1}
    if dup: problems.append(f"[D] decisions.md에 같은 D-번호 제목이 중복: {sorted(dup)}")
    refs = set(re.findall(r"\bD-\d+[a-z]?\b", "\n".join(docs.values())))
    missing = sorted(r for r in refs if r not in set(heads) and not any(h.startswith(r) for h in heads))
    if missing: warns.append(f"[D] 제목은 없는데 문서에서 인용되는 번호(후속·하위 번호일 수 있음): {missing}")

# ---------- E. results.csv ↔ 문서 ----------
rp = f"{ROOT}/outputs/tables/results.csv"
if os.path.exists(rp):
    r = pd.read_csv(rp); text = "\n".join(docs.values())
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

# ---------- F. 숫자 출처 점검 (문서 속 숫자가 노트북·표 어디에도 없으면 목록으로) ----------
NUM = re.compile(r"(?<![\w.])[−-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?p?|(?<![\w.])[−-]?\d+\.\d+%?p?|(?<![\w.])\d{3,}%?")
def numbers(s):
    out = []
    for m in NUM.finditer(s):
        t = m.group(0); out.append((m.start(), t))
    return out
def to_float(t):
    pct = "%" in t
    v = float(t.replace(",", "").replace("%p", "").replace("%", "").replace("−", "-"))
    return v, pct, (len(t.replace("%p", "").replace("%", "").split(".")[1]) if "." in t else 0)
src_text = ""
for p in notebooks:
    for c in nb_cells(p):
        src_text += "\n" + "".join(c["source"])
        for o in c.get("outputs", []):
            src_text += "\n" + ("".join(o.get("text", [])) if o.get("output_type") == "stream" else "".join(o.get("data", {}).get("text/plain", [])))
for p in glob.glob(f"{ROOT}/outputs/tables/*.csv"): src_text += "\n" + rd(p)
pool = set()
for _, t in numbers(src_text.replace("−", "-")):
    try: pool.add(float(t.replace(",", "").replace("%", "")))
    except: pass
for m in re.finditer(r"(?<![\w.])\d+(?:\.\d+)?", src_text):   # 작은 정수·소수도 풀에 포함
    try: pool.add(float(m.group(0)))
    except: pass
def found(v, pct, d):
    cands = {v} | ({v / 100} if pct else set()) | ({v * 100} if not pct and abs(v) < 1 else set())
    for f in pool:
        for c in cands:
            if abs(round(f, d) - c) < 1e-9 or abs(round(f * 100, d) - c) < 1e-9 and pct: return True
            if abs(round(f, d + 2) - round(c, d + 2)) < 1e-9 and pct: return True
    return False
ALL = "--all" in sys.argv
def day6_scope(d, s):
    if ALL: return s
    if d == "agenda": return s
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
            if abs(v) >= 1900 and abs(v) <= 2100 and not pct and dec == 0: continue
            if not found(v, pct, dec): unmatched.setdefault(d, []).append((ln, t, line.strip()[:90]))
for d, lst in unmatched.items():
    warns.append(f"[F] {d}.md({'전체' if ALL else 'Day 6 범위'}): 노트북·표에서 못 찾은 숫자 {len(lst)}개 (출처 셀과 직접 대조)")
    seen = set()
    for ln, t, ctx in lst:
        if (ln, t) in seen: continue
        seen.add((ln, t)); warns.append(f"      L{ln} {t}  …{ctx}")

os.makedirs(f"{ROOT}/tools", exist_ok=True)
open(f"{ROOT}/tools/check_report.txt", "w", encoding="utf-8").write("\n".join(problems + [""] + warns))
print("=== 오류 후보 (고쳐야 함) ===" if problems else "=== 오류 후보 없음 ===")
for x in problems: print(" ", x)
print("\n=== 확인 필요 (경고) ===" if warns else "\n=== 경고 없음 ===")
print("  (참고) F는 소수 1~2자리 숫자가 우연히 일치해 통과할 수 있어 통과가 정확하다는 보증은 아님. 큰 숫자·3자리 소수 위주로 해석.)")
for x in warns[:200]: print(" ", x)
if len(warns) > 200: print(f"  ... 외 {len(warns)-200}줄 (전체는 tools/check_report.txt)")
sys.exit(1 if problems else 0)
