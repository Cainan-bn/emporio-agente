from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from emporio.policies.chunker import PolicyChunk, split_sections
from emporio.policies.ingest import extract_pages
from emporio.text import normalize

# Calibração:
# - score >= 2.0 E pelo menos 2 tokens distintos do top1 casam
# - 1 token isolado só passa se score >= 2.0 (mas só 1 token não passa min=2)
# - Se top1 e top2 têm scores dentro de 10%, vence a seção anterior
#   (determinístico, não hardcoded por id)
_MIN_SCORE = 2.0

_STOPWORDS = frozenset(
    {
        "um",
        "uma",
        "uns",
        "umas",
        "o",
        "a",
        "os",
        "as",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "sem",
        "sob",
        "ate",
        "ou",
        "e",
        "mas",
        "que",
        "se",
        "como",
        "mais",
        "muito",
        "bem",
        "ja",
        "nao",
        "sim",
        "voce",
        "ele",
        "ela",
        "vos",
        "eu",
        "tu",
        "meu",
        "seu",
        "num",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "ao",
        "aos",
        "qual",
        "quais",
        "quanto",
        "quanta",
        "quantos",
        "quantas",
        "pra",
        "pro",
    }
)

_PARCELA_RE = re.compile(r"^(\d+)\s*x\s*$")
_VEZES_RE = re.compile(r"^(\d+)\s+vezes$")

# Stemmer simples para português.
# Ordem: advérbio (-mente), aumentativo (-ção/-ções),
# gerúndio (-ndo), plural (-s), 'ores'->'or', terminações verbais.
# Limitação: 'oes'->'ao' erra 'canoes' (inexistente no domínio).
_SYNONYM_GROUPS: list[tuple[str, list[str]]] = [
    (
        "devolucao",
        [
            "devolver",
            "devolucao",
            "reembolso",
            "reembolsar",
            "cancelar",
            "cancelamento",
            "arrependimento",
            "arrepender",
        ],
    ),
    ("troca", ["trocar", "troca", "trocas", "troque"]),
    (
        "frete_interior",
        [
            "dourados",
            "corumba",
            "ponta",
            "pora",
            "lagoas",
            "interior",
            "cidade",
            "cidades",
            "outra",
            "outras",
        ],
    ),
    ("frete", ["frete", "fretes", "entrega", "entregas", "envio", "envios"]),
    ("pix", ["pix", "a vista", "vista"]),
    (
        "parcelamento",
        [
            "parcelar",
            "parcela",
            "parcelamento",
            "pagar",
            "pagamento",
            "dividir",
            "divisao",
            "vezes",
            "vez",
        ],
    ),
    (
        "horario",
        [
            "horario",
            "horarios",
            "funcionamento",
            "abre",
            "abrem",
            "abrir",
            "fecha",
            "fechar",
            "aberto",
            "atende",
            "atendimento",
        ],
    ),
    ("contato", ["whatsapp", "zap", "celular", "telefone", "ligar", "contato", "contatar"]),
    (
        "dados_empresa",
        ["fisica", "presencial", "site", "cnpj", "loja", "vender", "vende", "vendem", "vendas"],
    ),
    ("endereco", ["endereco", "localizacao", "localizacao", "onde fica", "fica"]),
    (
        "defeito",
        [
            "defeito",
            "defeitos",
            "quebrado",
            "quebrada",
            "quebrados",
            "quebradas",
            "estragado",
            "estragada",
            "danificado",
            "riscado",
            "quebrou",
            "estragou",
        ],
    ),
    ("garantia", ["garantia", "garantias", "prazo", "prazos", "garantir"]),
    ("rastreio", ["rastrear", "rastreio", "rastreamento", "codigo", "pedido"]),
    (
        "acessorio",
        [
            "acessorio",
            "acessorios",
            "corda",
            "cordas",
            "palheta",
            "palhetas",
            "cabo",
            "cabos",
            "case",
            "pedal",
            "pedais",
            "amplificador",
            "amplificadores",
        ],
    ),
]

_SYNONYM_MAP: dict[str, str] = {}
for canonical, variants in _SYNONYM_GROUPS:
    for v in variants:
        _SYNONYM_MAP[v] = canonical


def _simple_stem(word: str) -> str:
    if len(word) <= 3:
        return word
    if word.endswith("mente"):
        return _simple_stem(word[:-5])
    if word.endswith("coes"):
        return word[:-4] + "cao"
    if word.endswith("ores") and len(word) > 4:
        return word[:-4] + "or"
    if word.endswith("oes") and len(word) > 4:
        return word[:-3] + "ao"
    if word.endswith("ndo") and len(word) > 4:
        return word[:-3] + "r"
    if word.endswith("s") and not word.endswith("ss"):
        singular = word[:-1]
        if len(singular) >= 2:
            return singular
    for suf in ["ar", "er", "ir", "or"]:
        if word.endswith(suf) and len(word) > 3:
            return word[: -len(suf)]
    return word


def _tokenize(text: str) -> list[str]:
    norm = normalize(text)
    raw_tokens = norm.split()
    result: list[str] = []
    for t in raw_tokens:
        if t in _STOPWORDS:
            continue
        if t.isdigit():
            continue
        m = _PARCELA_RE.match(t)
        if m:
            result.append("parcelamento")
            continue
        m2 = _VEZES_RE.match(norm)
        if m2 and m2.group(1) == t.split()[0] if " " in t else False:
            pass
        stemmed = _simple_stem(t)
        if stemmed:
            result.append(stemmed)
        syn = _SYNONYM_MAP.get(t)
        if syn:
            result.append(syn)
    return result


@dataclass
class PolicyHit:
    chunk: PolicyChunk
    score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", float(self.score))


class PolicyRetriever:
    def __init__(self, chunks: list[PolicyChunk]) -> None:
        self._chunks = chunks
        self._build_index()

    @classmethod
    def from_pdf(cls, pdf_path: str | Path) -> PolicyRetriever:
        pages = extract_pages(pdf_path)
        chunks = split_sections(pages)
        return cls(chunks)

    def _build_index(self) -> None:
        documents: list[str] = []
        for chunk in self._chunks:
            title = normalize(chunk.title) if chunk.title else ""
            parent = normalize(chunk.parent_title) if chunk.parent_title else ""
            text = f"{chunk.text} {title} {title} {title} {parent}"
            documents.append(text)
        tokenized = [_tokenize(d) for d in documents]
        self._bm25 = BM25Okapi(tokenized)

    def _count_matching(self, tokens: list[str], doc_idx: int) -> int:
        return sum(1 for t in tokens if self._bm25.get_scores([t])[doc_idx] > 0)

    def search(
        self,
        query: str,
        k: int = 3,
        include_internal: bool = False,
        min_score: float | None = None,
    ) -> list[PolicyHit]:
        if not query.strip():
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        threshold = min_score if min_score is not None else _MIN_SCORE
        min_match = min(2, len(tokens))

        scores = self._bm25.get_scores(tokens)
        candidates = []
        for i in range(len(self._chunks)):
            if scores[i] < threshold:
                continue
            matching = self._count_matching(tokens, i)
            if matching < min_match:
                continue
            chunk = self._chunks[i]
            if not include_internal and chunk.internal:
                continue
            candidates.append((scores[i], i, matching))

        if not candidates:
            return []

        candidates.sort(key=lambda x: (-x[0], -x[2], x[1]))

        # Tiebreaker: if top2 scores within 10%, prefer earlier section
        if len(candidates) >= 2:
            if candidates[1][0] >= candidates[0][0] * 0.9:
                if candidates[1][1] < candidates[0][1]:
                    candidates[0], candidates[1] = candidates[1], candidates[0]

        results = []
        for score, idx, _ in candidates:
            results.append(PolicyHit(chunk=self._chunks[idx], score=score))
            if len(results) >= k:
                break
                break
        return results

    def get_section(self, section_id: str) -> PolicyChunk | None:
        for chunk in self._chunks:
            if chunk.section_id == section_id:
                return chunk
        return None

    @property
    def chunks(self) -> list[PolicyChunk]:
        return list(self._chunks)
