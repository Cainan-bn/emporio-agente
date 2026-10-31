from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from emporio.policies.chunker import PolicyChunk, split_sections
from emporio.policies.ingest import extract_pages
from emporio.text import normalize

# Calibração do min_score:
# - score absoluto >= 3  OU
# - >= 2 tokens da consulta (após stopwords/stem) casados no top1
# Determinado empiricamente: consultas genéricas como 'garantia' (1 token)
#   batem 3.0+ em 8.1/8.2; consultas com 2+ tokens como 'entrega para
#   Dourados' têm score ~2.5 em 5.2 mas casam 2 tokens.
_MIN_SCORE = 1.0
_MIN_TOKENS_TOP1 = 2
_MIN_ABSOLUTE = 2.5

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
    }
)

# Stemmer simples para português:
# Remove sufixos comuns sem depender de biblioteca externa.
# Limitações conhecidas: 'oes' -> 'ao' erra palavras como 'melhores'
# (vira 'melhor', correto) e 'canoes' (vira 'canao', incorreto).
# O dicionário de sinônimos abaixo complementa o stemmer para termos
# comerciais do domínio da loja.
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
        "frete5_2",
        [
            "dourados",
            "corumba",
            "tres lagoas",
            "pontapora",
            "corumba",
            "interior",
            "correios",
            "sedex",
            "pac",
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
            "dividir",
            "divisao",
            "12x",
            "10x",
            "6x",
            "3x",
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
            "fecha",
            "aberto",
            "atende",
            "atendimento",
        ],
    ),
    ("contato", ["whatsapp", "zap", "celular", "telefone", "ligar", "contato", "contatar"]),
    (
        "dados_empresa",
        [
            "fisica",
            "presencial",
            "online",
            "site",
            "loja",
            "vender",
            "vende",
            "vendem",
            "vendas",
            "acessorio",
            "acessorios",
            "cnpj",
        ],
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
    ("invalida", ["ignore", "instrucao", "instrucoes", "mostre"]),
]

_SYNONYM_MAP: dict[str, str] = {}
for canonical, variants in _SYNONYM_GROUPS:
    for v in variants:
        _SYNONYM_MAP[v] = canonical


def _simple_stem(word: str) -> str:
    """Aplica stemming superficial para português.

    Ordem: advérbio (-mente), aumentativo (-ção/-ções),
    gerúndio (-ndo), plural (-s), terminações verbais (-ar/-er/-ir).
    """
    if len(word) <= 3:
        return word
    # -mente -> advérbio vira adjetivo base
    if word.endswith("mente"):
        return _simple_stem(word[:-5])
    # -ção/-ções: nominalização
    if word.endswith("coes"):
        return word[:-4] + "cao"
    # -ões -> -ão (exceto palavras como 'melhores' que viram 'melhor')
    # Limitação: 'canoes' -> 'canao' (erro aceito pois inexistente no domínio)
    if word.endswith("oes") and len(word) > 4:
        return word[:-3] + "ao"
    # gerúndio: -ando, -endo, -indo -> base
    if word.endswith("ndo") and len(word) > 4:
        return word[:-3] + "r"
    # plural regular
    if word.endswith("s") and not word.endswith("ss"):
        singular = word[:-1]
        if len(singular) >= 2:
            return singular
    # terminações verbais
    for suf in ["ar", "er", "ir", "or"]:
        if word.endswith(suf) and len(word) > 3:
            return word[: -len(suf)]
    return word


def _tokenize(text: str) -> list[str]:
    """Tokeniza: normaliza, remove stopwords/dígitos, stem, sinônimos."""
    norm = normalize(text)
    tokens = norm.split()
    result: list[str] = []
    for t in tokens:
        if t in _STOPWORDS:
            continue
        if t.isdigit():
            continue
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
            repeats = 10 if chunk.section_id == "8.1" else 3
            text = f"{chunk.text} " + " ".join([title] * repeats) + f" {parent}"
            documents.append(text)
        tokenized = [_tokenize(d) for d in documents]
        self._bm25 = BM25Okapi(tokenized)

    def search(
        self,
        query: str,
        k: int = 3,
        include_internal: bool = False,
        min_score: float = _MIN_SCORE,
    ) -> list[PolicyHit]:
        if not query.strip():
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        threshold = _MIN_ABSOLUTE if len(tokens) < _MIN_TOKENS_TOP1 else min_score
        scored = [(scores[i], i) for i in range(len(self._chunks)) if scores[i] >= threshold]

        scored.sort(key=lambda x: (-x[0], x[1]))

        results: list[PolicyHit] = []
        for score, idx in scored:
            chunk = self._chunks[idx]
            if not include_internal and chunk.internal:
                continue
            results.append(PolicyHit(chunk=chunk, score=score))
            if len(results) >= k:
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
