"""
Testes unitários para o HinoRecommender (Etapa 2.1).
Valida pesos explicáveis, normalização com acentos/diacríticos, remoção de stopwords,
desempate determinístico e geração de justificativas legíveis para humanos.
"""

import pytest
from src.models.hino import Hino
from src.services.hino_recommender import HinoRecommender, MatchReason, ScoredHino


@pytest.fixture
def recommender() -> HinoRecommender:
    return HinoRecommender()


def test_normalizacao_deterministica(recommender: HinoRecommender):
    """Testa se acentuação, pontuação e maiúsculas são normalizadas corretamente."""
    texto = "  Graça, Louvor & Oração!  Coração... "
    normalizado = recommender.normalize_text(texto)
    assert normalizado == "graca louvor oracao coracao"


def test_tokenizacao_com_stopwords(recommender: HinoRecommender):
    """Testa remoção de stopwords em português e tokens curtos."""
    texto = "O amor de Deus para com todos nós em Cristo"
    tokens = recommender.tokenize(texto)
    assert "amor" in tokens
    assert "deus" in tokens
    assert "cristo" in tokens
    assert "de" not in tokens
    assert "com" not in tokens
    assert "para" not in tokens
    assert "em" not in tokens


def test_pesos_nomeados_e_score_hino(recommender: HinoRecommender):
    """Verifica se os pesos por campo são aplicados corretamente."""
    hino = Hino(
        id=1,
        numero="1",
        titulo="Santo, Santo, Santo",
        categoria="Adoração",
        subcategoria="Santidade de Deus",
        texto_base="Apocalipse 4:8",
        letra="Santo, Santo, Santo, Deus onipotente",
    )
    temas = ["Santidade", "Reverência"]

    tokens = ["adoracao", "santidade"]
    scored = recommender.score_hino(hino, temas, tokens, query_normalizada="adoracao")

    # Match em Categoria (Adoração): +3
    # Match em Tema (Santidade): +4
    # Match em Subcategoria (Santidade de Deus): +3
    assert scored.score_total == 10
    campos_match = [r.campo for r in scored.reasons]
    assert "Categoria" in campos_match
    assert "Tema" in campos_match
    assert "Subcategoria" in campos_match


def test_titulo_exato_tem_peso_maximo(recommender: HinoRecommender):
    """Testa se a correspondência exata do título recebe peso máximo (10 pts)."""
    hino = Hino(
        id=10,
        numero="10",
        titulo="Grandioso És Tu",
        categoria="Louvor",
    )
    scored = recommender.score_hino(
        hino,
        temas_hino=[],
        tokens=["grandioso", "tu"],
        query_normalizada="grandioso es tu",
    )
    assert scored.score_total >= HinoRecommender.PESO_TITULO_EXATO
    assert any(r.campo == "Título" and r.pontos == 10 for r in scored.reasons)


def test_justificativa_legivel_humana(recommender: HinoRecommender):
    """Testa a geração da justificativa legível para humanos."""
    hino = Hino(
        id=15,
        numero="15",
        titulo="Castelo Forte",
        categoria="Segurança",
    )
    temas = ["Proteção Divina"]
    scored = recommender.score_hino(hino, temas, ["forte", "protecao"], "castelo forte")
    justificativa = scored.justificativa_legivel

    assert "Recomendado por correspondência em" in justificativa
    assert "Título" in justificativa
    assert "Castelo Forte" in justificativa or "Tema" in justificativa


def test_justificativa_fallback_sem_match():
    """Testa justificativa quando não há razões pontuadas."""
    hino = Hino(id=99, numero="99", titulo="Hino Genérico")
    scored = ScoredHino(hino=hino, score_total=0, reasons=[])
    assert "Recomendado por adequação geral" in scored.justificativa_legivel


def test_desempate_deterministico(recommender: HinoRecommender):
    """
    Testa se hinos com scores iguais são desempatados deterministicamente
    por número crescente e depois por título.
    """
    hino_a = Hino(id=1, numero="25", titulo="B Louvor", categoria="Geral")
    hino_b = Hino(id=2, numero="10", titulo="Z Louvor", categoria="Geral")
    hino_c = Hino(id=3, numero="100", titulo="A Louvor", categoria="Geral")

    candidatos = [hino_a, hino_b, hino_c]
    temas_map = {1: [], 2: [], 3: []}

    # Todos pontuam 0
    ranked = recommender.rank(candidatos, temas_map, "Inexistente", limit=3)
    # Ordem de desempate por número: 10 (hino_b), 25 (hino_a), 100 (hino_c)
    assert [s.hino.numero for s in ranked] == ["10", "25", "100"]
