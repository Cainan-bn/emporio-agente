"""Busca BM25 sobre as seções do manual de políticas, com citação da seção.

Como funciona (o manual tem ~25 seções, então um índice lexical simples basta — ADR-003):

1. **Tokenização**: `normalize` (sem acento/caixa), remoção de stopwords e *stemming*
   leve de português (`_stem`).
2. **Expansão da consulta (só do lado da consulta)**: palavras de cliente que não aparecem
   no manual ("devolver", "zap", "Dourados", "10x") ganham termos que *aparecem* no manual
   (`_EXPANSIONS`). Os documentos não são expandidos, para não diluir o ranking.
3. **Ranking por conceito**: BM25 (`rank_bm25`) calculado por termo da consulta; cada
   termo contribui **uma vez**: o melhor entre ele mesmo e suas expansões, mais um reforço
   (`_BONUS`) do outro quando a seção casa os dois. Assim expandir não infla a pontuação.
   O título da seção é repetido no documento indexado.
4. **Corte**: valem só seções com pontuação >= `_MIN_SCORE` e >= `_RELATIVE_CUTOFF` da melhor.
   Termos genéricos que casam por acaso (ex.: "atendimento") ficam abaixo do corte, enquanto
   termos específicos do manual (ex.: "cnpj", "jadlog") passam. Calibrado com a tabela de
   consultas de `tests/test_policy_retriever.py`.
5. **Desempate determinístico**: pontuações dentro de 5% da melhor desempatam pela ordem
   do documento (seção anterior primeiro).

A proteção contra vazamento de seções internas é `PolicyChunk.internal` (filtradas por
padrão), não palavras-chave na consulta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from emporio.policies.chunker import PolicyChunk, split_sections
from emporio.policies.ingest import extract_pages
from emporio.text import normalize

_MIN_SCORE = 1.5
_RELATIVE_CUTOFF = 0.5
_EXPANSION_WEIGHT = 1.0
_BONUS = 0.5
_TIE_MARGIN = 0.95
_TITLE_REPEAT = 5

# "online" e "loja" ficam nas stopwords: "loja" aparece em quase toda seção (baixa informação)
# e "online" puxava a seção 4.1 ("Compras Online") para perguntas sobre loja física.
_STOPWORDS = frozenset(
    "um uma uns umas o a os as de do da dos das em no na nos nas para pra pro por com sem "
    "sob ate ou e mas que se como mais muito bem ja nao sim voce voces ele ela eu meu minha "
    "seu sua pelo pela ao aos qual quais quanto quanta quantos quantas posso pode podem "
    "quero queria gostaria tem ter tenho ha vai ser sao foi dar da so tambem ainda depois "
    "antes quando onde online loja lojas".split()
)

_NUMERIC_INSTALLMENT = re.compile(r"^\d+x$")


def _stem(word: str) -> str:
    """Reduz plural, -mente, -ções e terminações verbais/agentivas comuns.

    Limitação conhecida: heurística simples, sem dicionário; 'melhores' -> 'melh'.
    Aplicada igualmente à indexação e à consulta, então o erro é consistente.
    """
    if len(word) <= 3:
        return word
    if word.endswith("mente") and len(word) > 7:
        word = word[:-5]
    if word.endswith("coes"):
        word = word[:-4] + "cao"
    elif word.endswith("oes"):
        word = word[:-3] + "ao"
    elif word.endswith("ores"):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    for suffix in ("ar", "er", "ir", "or"):
        if len(word) > 4 and word.endswith(suffix):
            return word[:-2]
    return word


# Palavras do cliente -> termos que aparecem no manual. Chaves e valores passam pelo `_stem`.
_EXPANSION_GROUPS: tuple[tuple[str, str], ...] = (
    (
        "devolver devolucao devolvo reembolso reembolsar cancelar cancelamento desistir "
        "arrepender arrependi arrependimento estorno",
        "arrependimento devolucao reembolso",
    ),
    ("trocar troca trocas troque", "troca"),
    (
        "dourados corumba ponta pora lagoas interior cidade outra outras fora estado",
        "correios pac sedex jadlog cidades",
    ),
    ("frete entrega entregam entregar envio enviar envia", "frete entrega"),
    ("pix vista", "pix vista desconto"),
    (
        "parcelar parcela parcelamento vezes dividir dividido pagar paga pago pagamento "
        "cartao credito",
        "parcelamento parcela credito pagamento",
    ),
    (
        "horario abrem abre abrir fecha fechar aberto funcionamento atende expediente "
        "feriado domingo sabado",
        "horario funcionamento",
    ),
    ("whatsapp zap celular telefone ligar contato contatar email", "telefone whatsapp"),
    ("fisica presencial endereco localizacao localiza fica rua", "endereco rua cep dados empresa"),
    (
        "acumula acumulam acumular acumulativa cumulativa cumulativo somar juntar",
        "cumulatividade cumulativas",
    ),
    ("lgpd privacidade excluir exclusao apagar", "lgpd pessoais exclusao"),
    ("cnpj razao social", "cnpj razao"),
    (
        "defeito defeitos quebrado quebrada quebrados quebradas quebrou estragado estragada "
        "estragou danificado danificada riscado riscada amassado amassada arranhado arranhada "
        "trincado trincada",
        "defeito fabricacao",
    ),
    ("fundada fundacao existe existir antiguidade historia", "fundada 2008 anos"),
    ("rastrear rastreio rastreamento codigo", "rastreamento codigo"),
    (
        "acessorio acessorios corda palheta cabo case pedal amplificador capa",
        "acessorios exclusivamente",
    ),
)


def _build_expansions() -> dict[str, tuple[str, ...]]:
    expansions: dict[str, tuple[str, ...]] = {}
    for keys, values in _EXPANSION_GROUPS:
        extra = tuple(dict.fromkeys(_stem(v) for v in values.split()))
        for key in keys.split():
            expansions[key] = extra
            expansions.setdefault(_stem(key), extra)
    return expansions


_EXPANSIONS = _build_expansions()


def _content_words(text: str) -> list[str]:
    """Palavras normalizadas sem stopwords e sem números soltos (preço vai em max_price)."""
    words = []
    for word in normalize(text).split():
        if word in _STOPWORDS or word.isdigit():
            continue
        words.append(word)
    return words


def _index_tokens(text: str) -> list[str]:
    return [_stem(w) for w in _content_words(text)]


def _query_terms(query: str) -> list[tuple[str, tuple[str, ...]]]:
    """Cada termo de conteúdo da consulta com seu stem e as expansões."""
    terms: list[tuple[str, tuple[str, ...]]] = []
    for word in _content_words(query):
        if _NUMERIC_INSTALLMENT.match(word):
            terms.append(("parcelamento", _EXPANSIONS["parcelamento"]))
            continue
        extra = _EXPANSIONS.get(word) or _EXPANSIONS.get(_stem(word)) or ()
        terms.append((_stem(word), extra))
    return terms


@dataclass(frozen=True)
class PolicyHit:
    """Trecho de política encontrado, com sua pontuação BM25 (float nativo)."""

    chunk: PolicyChunk
    score: float


class PolicyRetriever:
    """Índice BM25 sobre os fragmentos do manual."""

    def __init__(self, chunks: list[PolicyChunk]) -> None:
        self._chunks = list(chunks)
        documents = [self._document_tokens(c) for c in self._chunks]
        self._bm25 = BM25Okapi(documents)

    @staticmethod
    def _document_tokens(chunk: PolicyChunk) -> list[str]:
        title = " ".join([chunk.title] * _TITLE_REPEAT)
        return _index_tokens(f"{chunk.text} {title} {chunk.parent_title or ''}")

    @classmethod
    def from_pdf(cls, pdf_path: str | Path) -> PolicyRetriever:
        return cls(split_sections(extract_pages(pdf_path)))

    @property
    def chunks(self) -> list[PolicyChunk]:
        return list(self._chunks)

    def get_section(self, section_id: str) -> PolicyChunk | None:
        return next((c for c in self._chunks if c.section_id == section_id), None)

    def search(
        self,
        query: str,
        k: int = 3,
        include_internal: bool = False,
        min_score: float | None = None,
    ) -> list[PolicyHit]:
        """Devolve até `k` trechos relevantes, do mais para o menos relevante."""
        terms = _query_terms(query)
        if not terms:
            return []
        threshold = _MIN_SCORE if min_score is None else min_score
        scores = self._concept_scores(terms)

        candidates = [
            (scores[i], i)
            for i, chunk in enumerate(self._chunks)
            if scores[i] >= threshold and (include_internal or not chunk.internal)
        ]
        if not candidates:
            return []
        best = max(score for score, _ in candidates)
        candidates = [c for c in candidates if c[0] >= best * _RELATIVE_CUTOFF]
        candidates.sort(key=lambda item: (-item[0], item[1]))
        # dentro da margem de 5% da melhor vale a ordem do documento (seção anterior primeiro)
        near_best = sorted(
            (c for c in candidates if c[0] >= best * _TIE_MARGIN), key=lambda c: c[1]
        )
        ordered = near_best + [c for c in candidates if c[0] < best * _TIE_MARGIN]
        return [PolicyHit(self._chunks[i], score) for score, i in ordered[:k]]

    def _concept_scores(self, terms: list[tuple[str, tuple[str, ...]]]) -> list[float]:
        """Soma, por seção, a melhor pontuação BM25 de cada termo (próprio ou expandido)."""
        totals = [0.0] * len(self._chunks)
        for stem, extra in terms:
            own = self._bm25.get_scores([stem]).tolist()
            expanded = [self._bm25.get_scores([e]).tolist() for e in extra]
            for i in range(len(totals)):
                best_expansion = _EXPANSION_WEIGHT * max((e[i] for e in expanded), default=0.0)
                # o melhor vale inteiro; o outro reforça (a seção casa a palavra E o conceito)
                totals[i] += max(own[i], best_expansion) + _BONUS * min(own[i], best_expansion)
        return totals
