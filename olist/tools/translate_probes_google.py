import csv, html
from pathlib import Path
from google.cloud import translate_v2 as translate

TOOL = "Google API"

def find(name):
    hits = [p for p in Path.cwd().rglob(name) if ".venv" not in p.parts]
    assert len(hits) == 1, f"{name}: {len(hits)}개 발견 {hits}"
    return hits[0]

PROBES = find("stage3_translation_probes.csv")
RESULTS = find("stage3_translation_probe_results.csv")
print("probes :", PROBES)
print("results:", RESULTS)

client = translate.Client()
with open(PROBES, encoding="utf-8-sig", newline="") as f:
    probes = list(csv.DictReader(f))
texts = [p["pt_text"] for p in probes]          # 포르투갈어 문장만 보냄(정답 열 안 보냄)
res = client.translate(texts, source_language="pt", target_language="ko", format_="text")
by_id = {p["probe_id"]: html.unescape(r["translatedText"]) for p, r in zip(probes, res)}

with open(RESULTS, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
n = 0
for r in rows[1:]:
    if r[0] == TOOL:
        r[3] = by_id[r[2]]
        n += 1
assert n == 14, f"'{TOOL}' 행이 {n}개입니다. init을 먼저 실행하세요."
with open(RESULTS, "w", encoding="utf-8-sig", newline="") as f:
    csv.writer(f).writerows(rows)
print("filled", n, "rows;", len(texts), "sentences sent")