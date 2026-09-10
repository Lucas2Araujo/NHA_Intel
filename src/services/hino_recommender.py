"""
Módulo de Recomendação Heurística Explicável de Hinos.

Responsável por calcular a relevância de hinos para temas pastorais e intenções
de culto utilizando heurística ponderada, normalização textual determinística e
geração de justificativas legíveis para humanos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Sequence

from src.models.hino import Hino

# Stopwords padrão em língua portuguesa para filtragem litúrgica
STOPWORDS_DEFAULT: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "aquela",
        "aquelas",
        "aquele",
        "aqueles",
        "aquilo",
        "as",
        "com",
        "como",
        "da",
        "das",
        "de",
        "dela",
        "delas",
        "dele",
        "deles",
        "do",
        "dos",
        "e",
        "ela",
        "elas",
        "ele",
        "eles",
        "em",
        "entre",
        "era",
        "eram",
        "essa",
        "essas",
        "esse",
        "esses",
        "esta",
        "estas",
        "este",
        "estes",
        "isto",
        "na",
        "nas",
        "no",
        "nos",
        "nossa",
        "nossas",
        "nosso",
        "nossos",
        "num",
        "numa",
        "o",
        "os",
        "ou",
        "para",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "por",
        "qual",
        "quando",
        "que",
        "quem",
        "se",
        "sem",
        "seu",
        "seus",
        "sua",
        "suas",
        "tambem",
        "te",
        "tem",
        "temos",
        "teu",
        "teus",
        "tu",
        "tua",
        "tuas",
        "um",
        "uma",
        "umas",
        "uns",
        "voce",
        "voces",
        "vos",
    }
)


@dataclass(frozen=True)
class MatchReason:
    """Representa uma evidência pontuada de correspondência de termo em um campo."""

    campo: str
    termo: str
    pontos: int
    detalhe: str = ""

    def formatar(self) -> str:
        """Gera texto explicativo resumido da correspondência."""
        if self.detalhe:
            return f"{self.campo} ('{self.detalhe}': +{self.pontos} pts)"
        return f"{self.campo} (+{self.pontos} pts)"


@dataclass
class ScoredHino:
    """Resultado da avaliação heurística de um hino com pontuação e justificativas."""

    hino: Hino
    score_total: int
    reasons: list[MatchReason] = field(default_factory=list)

    @property
    def justificativa_legivel(self) -> str:
        """Gera uma explicação em linguagem natural do porquê o hino foi recomendado."""
        if not self.reasons:
            return "Recomendado por adequação geral ao contexto do culto."

        # Agrupa evidências por campo para evitar repetições
        evidencias_por_campo: dict[str, list[str]] = {}
        for r in self.reasons:
            det = f"'{r.detalhe}'" if r.detalhe else f"'{r.termo}'"
            evidencias_por_campo.setdefault(r.campo, []).append(det)

        partes: list[str] = []
        for campo, detalhes in evidencias_por_campo.items():
            detalhes_unicos = list(dict.fromkeys(detalhes))
            detalhes_str = ", ".join(detalhes_unicos[:2])
            partes.append(f"{campo}: {detalhes_str}")

        return f"Recomendado por correspondência em {'; '.join(partes)}."


class HinoRecommender:
    """
    Motor heurístico explicável para ranking e recomendação de hinos.

    Utiliza pesos nomeados por campo, normalização determinística e
    critérios estritos de desempate para garantir reproducibilidade.
    """

    # Pesos nomeados por campo
    PESO_TITULO_EXATO: int = 10
    PESO_TITULO_PARCIAL: int = 5
    PESO_TEMA: int = 4
    PESO_CATEGORIA: int = 3
    PESO_SUBCATEGORIA: int = 3
    PESO_TEXTO_BASE: int = 2
    PESO_LETRA: int = 1

    def __init__(self, stopwords: set[str] | frozenset[str] | None = None):
        self.stopwords: frozenset[str] = (
            frozenset(stopwords) if stopwords is not None else STOPWORDS_DEFAULT
        )

    @staticmethod
    def normalize_text(text: str | None) -> str:
        """
        Normaliza o texto deterministicamente:
        1. Remove acentos e diacríticos (NFKD).
        2. Converte para minúsculas (case folding).
        3. Substitui pontuações por espaços.
        4. Remove espaços múltiplos.
        """
        if not text:
            return ""
        # Decomposição canônica de caracteres acentuados
        nfkd = unicodedata.normalize("NFKD", text)
        sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
        # Substitui caracteres não alfanuméricos por espaço
        limpo = re.sub(r"[^\w\s]", " ", sem_acento.lower())
        return " ".join(limpo.split())

    def tokenize(self, text: str | None) -> list[str]:
        """
        Converte uma string em uma lista determinística de palavras-chave normalizadas,
        filtrando stopwords e tokens muito curtos (<= 2 caracteres).
        """
        if not text:
            return []
        norm = self.normalize_text(text)
        palavras = norm.split()
        return [p for p in palavras if len(p) > 2 and p not in self.stopwords]

    def score_hino(
        self,
        hino: Hino,
        temas_hino: list[str],
        tokens: list[str],
        query_normalizada: str = "",
    ) -> ScoredHino:
        """
        Calcula a pontuação de relevância de um único hino para os tokens fornecidos,
        registrando cada motivo de pontuação (MatchReason).
        """
        reasons: list[MatchReason] = []
        score_total = 0

        titulo_norm = self.normalize_text(hino.titulo)
        categoria_norm = self.normalize_text(hino.categoria or "")
        subcategoria_norm = self.normalize_text(hino.subcategoria or "")
        texto_base_norm = self.normalize_text(hino.texto_base or "")
        letra_norm = self.normalize_text(hino.letra or "")

        # 1. Checagem de Título Exato ou Frase Completa da Query
        if query_normalizada and query_normalizada in titulo_norm:
            pontos = self.PESO_TITULO_EXATO
            score_total += pontos
            reasons.append(
                MatchReason(
                    campo="Título",
                    termo=query_normalizada,
                    pontos=pontos,
                    detalhe=hino.titulo,
                )
            )

        # 2. Avaliação de Temas Relacionados
        temas_normalizados = [
            (t, self.normalize_text(t)) for t in temas_hino if t.strip()
        ]
        temas_pontuados: set[str] = set()

        for token in tokens:
            # Match no Título (se já não pontuou como exato da query inteira)
            if token in titulo_norm and (
                not query_normalizada or query_normalizada not in titulo_norm
            ):
                score_total += self.PESO_TITULO_PARCIAL
                reasons.append(
                    MatchReason(
                        campo="Título",
                        termo=token,
                        pontos=self.PESO_TITULO_PARCIAL,
                        detalhe=hino.titulo,
                    )
                )

            # Match nos Temas
            for tema_orig, tema_n in temas_normalizados:
                if token in tema_n and tema_orig not in temas_pontuados:
                    temas_pontuados.add(tema_orig)
                    score_total += self.PESO_TEMA
                    reasons.append(
                        MatchReason(
                            campo="Tema",
                            termo=token,
                            pontos=self.PESO_TEMA,
                            detalhe=tema_orig,
                        )
                    )

            # Match em Categoria
            if categoria_norm and token in categoria_norm:
                score_total += self.PESO_CATEGORIA
                reasons.append(
                    MatchReason(
                        campo="Categoria",
                        termo=token,
                        pontos=self.PESO_CATEGORIA,
                        detalhe=hino.categoria or "",
                    )
                )

            # Match em Subcategoria
            if subcategoria_norm and token in subcategoria_norm:
                score_total += self.PESO_SUBCATEGORIA
                reasons.append(
                    MatchReason(
                        campo="Subcategoria",
                        termo=token,
                        pontos=self.PESO_SUBCATEGORIA,
                        detalhe=hino.subcategoria or "",
                    )
                )

            # Match em Texto Bíblico Base
            if texto_base_norm and token in texto_base_norm:
                score_total += self.PESO_TEXTO_BASE
                reasons.append(
                    MatchReason(
                        campo="Texto Bíblico",
                        termo=token,
                        pontos=self.PESO_TEXTO_BASE,
                        detalhe=hino.texto_base or "",
                    )
                )

            # Match na Letra (apenas se houver letra disponível e não tiver match em outros campos)
            if letra_norm and token in letra_norm and not reasons:
                score_total += self.PESO_LETRA
                reasons.append(
                    MatchReason(
                        campo="Letra",
                        termo=token,
                        pontos=self.PESO_LETRA,
                        detalhe="Trecho da letra",
                    )
                )

        return ScoredHino(hino=hino, score_total=score_total, reasons=reasons)

    def rank(
        self,
        candidatos: Sequence[Hino],
        temas_map: dict[int, list[str]],
        query: str,
        limit: int = 6,
    ) -> list[ScoredHino]:
        """
        Ranqueia os hinos candidatos de forma explicável e determinística.

        Desempate determinístico:
        1. `score_total` decrescente
        2. `numero` numérico crescente (ou alfanumérico)
        3. `titulo` alfabético crescente
        """
        query_norm = self.normalize_text(query)
        tokens = self.tokenize(query)

        scored_list: list[ScoredHino] = []
        for hino in candidatos:
            if hino.id is None:
                continue
            temas = temas_map.get(hino.id, [])
            scored = self.score_hino(hino, temas, tokens, query_norm)
            scored_list.append(scored)

        def desempate_key(item: ScoredHino) -> tuple[int, int, str]:
            num_int = (
                int(re.sub(r"\D", "", item.hino.numero))
                if re.sub(r"\D", "", item.hino.numero)
                else 9999
            )
            # Como queremos score DESC e os outros ASC, invertemos o score
            return (-item.score_total, num_int, item.hino.titulo)

        scored_list.sort(key=desempate_key)
        return scored_list[:limit]
