"""hold-out을 여는 도구가 맨 먼저 부르는 동결 확인 (규칙 문서 §2, §6-2).

hold-out 원문·번역·라벨을 다루는 모든 스크립트는 --freeze-commit 과 --rules-sha 를 받아 여기서 확인한 뒤에만 진행한다.
확인 내용
  1) 동결 커밋이 저장소에 있고 현재 HEAD의 조상이다
  2) 그 커밋에 tools/kw_rules.py 가 들어 있다
  3) 지금 작업 폴더의 tools/kw_rules.py 가 그 커밋의 것과 같다(동결 후 수정 없음)
  4) kw_rules.file_sha256() 이 --rules-sha 와 같다
하나라도 어긋나면 중단한다. 이 모듈은 규칙을 돌리지 않고 hold-out 파일도 열지 않는다.
"""
import subprocess
import sys

RULES_PATH = "tools/kw_rules.py"


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def assert_frozen(freeze_commit, rules_sha, echo=True):
    rc, full, err = _git("rev-parse", "--verify", f"{freeze_commit}^{{commit}}")
    assert rc == 0, f"동결 커밋을 찾을 수 없음: {freeze_commit} ({err})"
    rc, _, _ = _git("merge-base", "--is-ancestor", full, "HEAD")
    assert rc == 0, "동결 커밋이 현재 HEAD의 조상이 아님"
    rc, _, _ = _git("cat-file", "-e", f"{full}:./{RULES_PATH}")
    assert rc == 0, f"동결 커밋에 {RULES_PATH} 가 없음"
    rc, _, _ = _git("diff", "--quiet", full, "--", RULES_PATH)
    assert rc == 0, f"{RULES_PATH} 가 동결 커밋과 다름(동결 후 수정됨). 이 상태로는 hold-out을 열지 않는다"
    if "tools" not in sys.path:
        sys.path.insert(0, "tools")
    import kw_rules
    got = kw_rules.file_sha256()
    assert got == rules_sha, f"kw_rules.py 해시 불일치: 현재 {got}, 지정 {rules_sha}"
    rc, when, _ = _git("show", "-s", "--format=%cI", full)
    msg = f"[ok] 동결 확인: 커밋 {full[:10]} ({when}), kw_rules.py sha256 {got}"
    if echo:
        print(msg)
    return full, got, msg
