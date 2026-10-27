"""키워드 규칙 (3단계 규칙 문서 §6-2). 동결 커밋에는 이 파일만 들어간다.

- 이 파일은 데이터 파일을 읽지 않는다(hold-out 경로를 참조하지 않음). 난수도 없다.
- 규칙 전체 = 아래의 RULES + 선택 로직(classify) + 정규화(norm) + 부정어 보호(first_match).
  증거 해시는 RULES 딕셔너리가 아니라 이 파일 전체의 sha256(file_sha256)을 쓴다.
- 평가 단위는 주 유형. 규칙은 P9를 내지 않고, 하나도 안 걸리면 '미분류'.
- 한 리뷰에 여러 유형이 걸리면 "원문에서 먼저 나온 유형"을 쓴다(코드북 규칙 3의 원칙). 예외 두 가지:
  (A) 부분 도착 표지가 있으면 P6b 대신 P3 (코드북 규칙 4: 일부라도 받았으면 P3)
  (B) 환불·교환 요구 단어로만 걸린 P4는, 같은 글에 P1·P2·P3 표현이 있으면 그쪽을 쓴다(요구는 문제의 결과)
"""
import hashlib
import re
import unicodedata

ORDER = ["P1", "P2", "P3", "P4", "P5", "P6a", "P6b"]

# 불용어: 부정어가 들어 있으면 안 된다(규칙 §6-2, §9). 현재 매칭에는 쓰이지 않는 목록이라
# assert는 형식상의 확인이다. 실제 부정어 보호는 NEG_GUARD_TYPES / first_match가 한다.
STOPWORDS = {"a", "o", "e", "de", "do", "da", "dos", "das", "um", "uma", "em", "no", "na",
             "que", "para", "por", "com", "os", "as", "ao", "se", "foi", "meu", "minha"}
NEGATIONS = {"não", "nao", "nem", "sem", "nunca", "nada"}

RULES = {
    "P1": [r"\bquebrad", r"\bdefeito", r"\bdanific", r"\bestrag", r"\bamassad", r"\brasgad",
           r"\bquebrou", r"\brachou", r"\bvazou", r"\bmofo", r"\bsujo", r"\busado", r"\bcheiro",
           r"\bpessim", r"\bruim", r"\bbaixa qualidade", r"\bnao presta", r"\bdescascou",
           r"\bqualidade", r"\bnao funciona", r"\bnao liga", r"\bmal feito", r"\bmau estado",
           r"\bpessima qualidade", r"\bfragil"],
    "P2": [r"\bdiferente d[oa] (anuncio|foto|descricao)", r"\bnao corresponde", r"\bnao condiz",
           r"\bpropaganda enganosa", r"\banuncio", r"\bfoto\b", r"\bdescricao", r"\bimagem"],
    "P3": [r"\bum dos (produtos|itens|pedidos)", r"\bo outro (nao|ainda)", r"\bos outros",
           r"\bapenas (um|uma|1|dois|duas|2)", r"\bsomente (um|uma|1)", r"\bso (chegou|veio|recebi)",
           r"\bnao veio", r"\bparte d[oa] (pedido|compra)", r"\bproduto errado", r"\boutro produto",
           r"\bveio errado", r"\bveio outro", r"\bfalt(ou|ando|a)\b", r"\bincompleto",
           r"\bcor errada", r"\bmodelo diferente", r"\bdiferente do que (pedi|comprei|solicitei)",
           r"\bdivergente"],
    "P4": [r"\bvendedor", r"\batendimento", r"\breembols", r"\bestorn", r"\bdevolu", r"\btroca",
           r"\bcancel", r"\bresposta", r"\bresponde", r"\bsac\b", r"\bsuporte (tecnico|ao cliente)"],
    "P5": [r"\bpreco", r"\bcaro\b", r"\bvalor", r"\bexpectativa", r"\besperava", r"\bnao vale",
           r"\bnao compensa", r"\bdecepcion", r"\bfrustr"],
    "P6a": [r"\batras", r"\bdemor", r"\bfora do prazo", r"\bpassou do prazo", r"\balem do prazo",
            r"\bestourou o prazo", r"\bnao chegou no prazo", r"\bmuito tempo"],
    "P6b": [r"\bnao chegou", r"\bnunca chegou", r"\bnao recebi", r"\bnao foi entregue",
            r"\bnao entregu", r"\baguardando", r"\bainda nao (chegou|recebi)", r"\bficamos esperando"],
}

# (A) 부분 도착 표지: P6b가 이겼더라도 이 표지가 글 어디에든 있으면 P3로 돌린다.
PARTIAL_MARKERS = [r"\bcompleto", r"\bquantidade", r"\bfalt(ou|ando)\b",
                   r"\btod(o|a)s (os |as )?(produto|iten|item)", r"\bso \d", r"\bsomente \d",
                   r"\bum dos\b", r"\bo outro\b", r"\bapenas (um|uma|1)\b",
                   # 2026-10-26 2차: 남은 P3→P6b 7건에서 확인한 표현 유형(수량 한정·일부 도착·다른 상품)
                   r"\bso (foi |foram )?(entregue|entregou|mandaram|enviaram|enviou|veio|vieram|chegou|recebi)",
                   r"\bapenas (o|a|os|as|dois|duas|\d+)\b", r"\bpela metade", r"\bparcialmente",
                   r"\b\d+ dos \d+", r"\bproduto correto",
                   r"\bnao (foi|era) o que (encomendei|pedi|comprei|solicitei)"]

# (B) 환불·교환 '요구' 단어. P4가 이 단어로만 걸렸을 때 다른 원인 표현이 있으면 그쪽을 쓴다.
REMEDY_PATTERNS = {r"\breembols", r"\bestorn", r"\bdevolu", r"\btroca", r"\bcancel"}

NEG_GUARD_TYPES = {"P6a", "P5"}
NEG_TOKENS = {"nao", "nem", "nunca", "sem", "nada"}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def assert_no_negation_in_stopwords():
    stop_norm = {norm(s) for s in STOPWORDS}
    bad = {w for w in NEGATIONS | {norm(n) for n in NEGATIONS} if w in STOPWORDS or norm(w) in stop_norm}
    assert not bad, f"불용어에 부정어가 들어 있음: {bad}"


def first_match(t, typ, pat):
    """패턴의 첫 유효 매칭 위치(없으면 None). 일부 유형은 앞 3단어에 부정어가 있으면 그 매칭을 무시한다."""
    for m in re.finditer(pat, t):
        if typ in NEG_GUARD_TYPES and not pat.startswith(r"\bnao"):
            prev = re.findall(r"\w+", t[:m.start()])[-3:]
            if any(w in NEG_TOKENS for w in prev):
                continue
        return m.start()
    return None


def classify(text, partial_override=True, remedy_demote=True):
    """리뷰 원문(포르투갈어) -> 유형 코드 또는 '미분류'. 두 플래그는 개발용 비교에만 끈다(기본은 둘 다 켬)."""
    n = norm(text)
    hits = {}          # 유형 -> (가장 이른 위치, 그 패턴)
    p4_conduct = False  # P4에 요구 단어가 아닌 응대 단어도 걸렸는가
    for typ, pats in RULES.items():
        for p in pats:
            pos = first_match(n, typ, p)
            if pos is None:
                continue
            if typ not in hits or pos < hits[typ][0]:
                hits[typ] = (pos, p)
            if typ == "P4" and p not in REMEDY_PATTERNS:
                p4_conduct = True
    if not hits:
        return "미분류"
    winner = min(hits.items(), key=lambda kv: kv[1][0])[0]
    if remedy_demote and winner == "P4" and not p4_conduct:
        others = {k: v for k, v in hits.items() if k in ("P1", "P2", "P3")}
        if others:
            winner = min(others.items(), key=lambda kv: kv[1][0])[0]
    if partial_override and winner == "P6b" and any(re.search(p, n) for p in PARTIAL_MARKERS):
        winner = "P3"
    return winner


def file_sha256():
    """이 파일 전체의 sha256 앞 12자리(동결 증거용). 줄바꿈(CRLF/LF) 차이를 없애고 계산한다."""
    with open(__file__, "rb") as f:
        data = f.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:12]
