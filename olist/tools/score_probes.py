"""번역 프로브 채점 (3단계 번역 도구 선정용)
사용법 (olist 폴더에서 실행):
  1) python tools/score_probes.py init "도구명" "버전"   # 결과 파일에 14행 빈칸 추가
  2) 결과 CSV의 output(번역문)·pass(Y/N) 칸을 채움 (판단 기준: probes.csv의 expected_meaning_ko)
  3) python tools/score_probes.py score                 # 기준 대비 통과/미달 출력
프로브는 가짜 문장이므로 실제 리뷰(hold-out 포함)와 무관하다.
"""
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")   # Code Runner(파이프) 출력이 cp949로 나가 깨지는 것 방지
sys.stderr.reconfigure(encoding="utf-8")

DOCS = Path("docs")
PROBES = DOCS / "stage3_translation_probes.csv"
RESULTS = DOCS / "stage3_translation_probe_results.csv"

# 시험 전에 고정한 필수 기준 (바꾸려면 시험 전에, 사유를 로그에 남길 것)
CRITERIA = {"부정어·악센트": 5, "frete 구분": 3, "환불·교환": 2}
REFERENCE_ONLY = ["구어체"]          # 못 넘어도 탈락 아님, 한계로 기록


def init(tool, version):
    probes = pd.read_csv(PROBES, encoding="utf-8-sig")
    new = pd.DataFrame({"tool": tool, "version": version, "probe_id": probes.probe_id,
                        "output": "", "pass": ""})
    if RESULTS.exists():
        old = pd.read_csv(RESULTS, encoding="utf-8-sig", dtype=str).fillna("")
        if ((old.tool == tool) & (old.version == version)).any():
            sys.exit(f"이미 있음: {tool} {version} (덮어쓰기 방지)")
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    new.to_csv(RESULTS, index=False, encoding="utf-8-sig")
    print(f"추가: {tool} {version} → {RESULTS}")


def score():
    probes = pd.read_csv(PROBES, encoding="utf-8-sig")
    sizes = probes.groupby("group").size()
    res = pd.read_csv(RESULTS, encoding="utf-8-sig", dtype=str).fillna("")
    res["probe_id"] = res.probe_id.astype(int)
    res = res.merge(probes[["probe_id", "group"]], on="probe_id", how="left")
    res["p"] = res["pass"].str.strip().str.upper()
    summary = []
    for (tool, ver), g in res.groupby(["tool", "version"], sort=False):
        print(f"\n[{tool} {ver}]")
        if len(g) != len(probes) or not g.p.isin(["Y", "N"]).all():
            print("  채점이 덜 끝남(pass 칸에 Y/N이 모두 있어야 함) → 건너뜀")
            continue
        ok = g.assign(ok=g.p.eq("Y")).groupby("group").ok.sum()
        passed = True
        for grp, need in CRITERIA.items():
            hit = int(ok.get(grp, 0))
            flag = "통과" if hit >= need else "미달"
            passed &= hit >= need
            print(f"  {grp}: {hit}/{sizes[grp]} (필수 {need}) {flag}")
        for grp in REFERENCE_ONLY:
            print(f"  {grp}: {int(ok.get(grp, 0))}/{sizes[grp]} (참고)")
        total = int(g.p.eq("Y").sum())
        print(f"  합계 {total}/{len(probes)} → {'필수 기준 통과' if passed else '필수 기준 미달'}")
        summary.append((tool, ver, total, passed))
    cand = sorted([s for s in summary if s[3]], key=lambda s: -s[2])
    print("\n주 도구 후보(통과 수 순):", [(t, v, n) for t, v, n, _ in cand] or "없음 → 한계 문구 규칙 적용")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "init" and len(sys.argv) == 4:
        init(sys.argv[2], sys.argv[3])
    elif cmd == "score":
        score()
    else:
        print(__doc__)
