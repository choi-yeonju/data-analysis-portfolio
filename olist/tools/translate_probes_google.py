"""번역 프로브 14문장을 Google Cloud Translation API(Basic v2)로 번역해 결과 파일에 채운다 (3단계 번역 도구 선정용, 2026-10-16).

  python tools/translate_probes_google.py      # olist 폴더, (.venv). Google Cloud 인증(ADC) 필요

- 입력: docs/stage3_translation_probes.csv (포르투갈어 문장만 보냄, 정답 열은 보내지 않음)
- 출력: docs/stage3_translation_probe_results.csv 의 "Google API" 행 14개 (먼저 score_probes.py init 으로 행을 만들어 둘 것)
- 리뷰 원문은 다루지 않는다(가짜 문장 14개만).
"""
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