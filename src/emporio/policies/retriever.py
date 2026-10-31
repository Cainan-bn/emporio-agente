from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from emporio.policies.chunker import PolicyChunk, split_sections
from emporio.policies.ingest import extract_pages
from emporio.text import normalize

_MIN_SCORE = 1.5  # calibrado nos testes; abaixo disso considera sem resultado
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
    }
)
_SIMILARITY_THRESHOLD = 0.7  # p/ sinônimos

_SYNONYM_GROUPS: list[tuple[str, list[str]]] = [
    ("devolucao", ["devolver", "devolucao", "reembolso", "reembolsar", "cancelar", "cancelamento"]),
    ("troca", ["trocar", "troca", "trocas"]),
    ("frete", ["frete", "fretes", "entrega", "entregas", "envio", "envios"]),
    ("pix", ["pix", "a vista", "vista"]),
    ("parcelamento", ["parcelar", "parcela", "parcelamento", "12x", "6x", "3x"]),
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
    ("endereco", ["endereco", "localizacao", "localizacao", "onde fica", "fica"]),
    ("defeito", ["defeito", "defeitos", "quebrado", "quebrou", "estragado", "estragou"]),
    ("garantia", ["garantia", "garantias", "prazo", "prazos"]),
    ("loja", ["loja", "vender", "vende", "vendem", "vendas", "acessorio", "acessorios"]),
]

_SYNONYM_MAP: dict[str, str] = {}
for canonical, variants in _SYNONYM_GROUPS:
    for v in variants:
        _SYNONYM_MAP[v] = canonical


def _simple_stem(word: str) -> str:
    if len(word) <= 3:
        return word
    suffixes = [
        ("mente", ""),
        ("coes", "cao"),
        ("oes", "ao"),
        ("ndo", "r"),
        ("ndo", ""),
    ]
    for suffix, replacement in suffixes:
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith("s") and not word.endswith("ss"):
        singular = word[:-1]
        if len(singular) >= 2:
            return singular
    for suffix in ["ar", "er", "ir", "or"]:
        if word.endswith(suffix) and len(word) > 3:
            return word[: -len(suffix)]
    return word


def _tokenize(text: str) -> list[str]:
    norm = normalize(text)
    tokens = norm.split()
    result = []
    for t in tokens:
        if t in _STOPWORDS:
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


class PolicyRetriever:
    def __init__(self, chunks: list[PolicyChunk]) -> None:
        self._chunks = chunks
        self._index: dict[str, Any] = {}
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
            # Repeat title for extra weight
            text = f"{chunk.text} {title} {title} {parent}"
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
        scored = [(scores[i], i) for i in range(len(self._chunks)) if scores[i] >= min_score]
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
