import re
from typing import Any

from src.models.hino import Hino
from src.repositories.hino_repository import HinoRepository

NOMES_BLOCOS_LITURGICOS = [
    "1. Abertura & Adoração",
    "2. Oração & Comunhão",
    "3. Louvor & Gratidão",
    "4. Mensagem & Edificação",
    "5. Reflexão & Meditação",
    "6. Consagração & Entrega",
    "7. Intercessão",
    "8. Testemunho & Partilha",
    "9. Esperança & Promessas",
    "10. Encerramento & Bênção",
]


class AgenteService:
    """
    Serviço assíncrono do Agente Organizador de Cultos.
    Realiza busca semântica e pontuação temática sobre os 601 hinos para gerar
    playlists de culto estruturadas por blocos litúrgicos.
    """

    def __init__(self, hino_repository: HinoRepository):
        self.hino_repository = hino_repository
        # Cache in-memory de hinos completos para scoring (carregado lazy)
        self._hinos_completos_cache: dict[int, Hino] | None = None

    async def _fetch_hinos_completos(self) -> dict[int, Hino]:
        """Busca todos os hinos com dados completos no repositório."""
        if hasattr(self.hino_repository, "get_all_complete"):
            all_hinos = await self.hino_repository.get_all_complete()
            return {h.id: h for h in all_hinos if h.id is not None}

        # Fallback para repositórios sem get_all_complete
        all_hinos = await self.hino_repository.get_all()
        result: dict[int, Hino] = {}
        for h in all_hinos:
            if h.id is None:
                continue
            hino = await self.hino_repository.get_by_id(h.id)
            if hino:
                result[h.id] = hino
        return result

    async def _get_hinos_completos(self) -> dict[int, Hino]:
        """Carrega e cacheia todos os hinos com campos completos para scoring."""
        if self._hinos_completos_cache is None:
            self._hinos_completos_cache = await self._fetch_hinos_completos()
        return self._hinos_completos_cache

    async def _get_temas_por_hino(self, hino_id: int) -> list[str]:
        """Retorna os temas associados a um hino via tabela de junção."""
        metadados = await self.hino_repository.get_metadados_relacionados(hino_id)
        return metadados.get("temas", [])

    def _extrair_palavras_chave(self, prompt: str) -> list[str]:
        """Extrai palavras-chave relevantes (>2 caracteres) do prompt."""
        prompt_clean = prompt.strip().lower()
        palavras = re.findall(r"\w+", prompt_clean)
        return [p for p in palavras if len(p) > 2]

    async def _gerar_playlist_padrao(self, num_hinos: int) -> dict[str, Any]:
        """Gera uma playlist padrão de adoração quando o prompt estiver vazio."""
        hinos = await self.hino_repository.search("Santo")
        hinos_selecionados = (
            hinos[:num_hinos]
            if len(hinos) >= num_hinos
            else await self.hino_repository.get_all()
        )
        return self._estruturar_blocos("Culto Geral", hinos_selecionados[:num_hinos])

    def _add_candidate_ids(
        self,
        candidatos: list[int],
        vistos: set[int],
        hinos: list[Hino],
        limite: int | None = None,
    ) -> None:
        """Adiciona IDs de hinos não duplicados à lista de candidatos."""
        for h in hinos:
            if h.id is not None and h.id not in vistos:
                vistos.add(h.id)
                candidatos.append(h.id)
                if limite and len(candidatos) >= limite:
                    break

    async def _buscar_candidatos_ids(
        self, palavras_relevantes: list[str], num_hinos: int
    ) -> list[int]:
        """Busca IDs de hinos candidatos no repositório com base nas palavras-chave."""
        candidatos_ids: list[int] = []
        vistos: set[int] = set()

        for kw in palavras_relevantes:
            resultados = await self.hino_repository.search(kw)
            self._add_candidate_ids(candidatos_ids, vistos, resultados)

        # Complementa com hinos adicionais se houver poucos candidatos
        if len(candidatos_ids) < num_hinos:
            todos = await self.hino_repository.get_all()
            self._add_candidate_ids(candidatos_ids, vistos, todos, limite=num_hinos * 3)

        return candidatos_ids

    async def _carregar_temas_candidatos(
        self, candidatos_ids: list[int]
    ) -> dict[int, list[str]]:
        """Carrega os temas dos hinos candidatos."""
        temas_por_hino: dict[int, list[str]] = {}
        for hino_id in candidatos_ids[:30]:
            temas_por_hino[hino_id] = await self._get_temas_por_hino(hino_id)
        return temas_por_hino

    def _calcular_score_hino(
        self,
        hino: Hino | None,
        temas_hino: list[str],
        palavras_relevantes: list[str],
    ) -> int:
        """Calcula a pontuação semântica de relevância de um hino."""
        if not hino:
            return 0

        campos = [
            (hino.titulo.lower(), 5),
            ((hino.categoria or "").lower(), 3),
            ((hino.subcategoria or "").lower(), 3),
            ((hino.texto_base or "").lower(), 2),
            (" ".join(t.lower() for t in temas_hino), 4),
        ]

        score = 0
        for kw in palavras_relevantes:
            for texto_campo, peso in campos:
                if kw in texto_campo:
                    score += peso

        return score

    def _selecionar_melhores_candidatos(
        self,
        candidatos_ids: list[int],
        hinos_completos: dict[int, Hino],
        temas_por_hino: dict[int, list[str]],
        palavras_relevantes: list[str],
        num_hinos: int,
    ) -> list[Hino]:
        """Ranqueia e retorna os N melhores hinos de acordo com o score."""

        def get_score(hid: int) -> int:
            return self._calcular_score_hino(
                hinos_completos.get(hid),
                temas_por_hino.get(hid, []),
                palavras_relevantes,
            )

        candidatos_ordenados = sorted(candidatos_ids, key=get_score, reverse=True)
        hinos_finais_ids = candidatos_ordenados[:num_hinos]

        hinos_finais = []
        for hid in hinos_finais_ids:
            hino = hinos_completos.get(hid)
            if hino:
                hinos_finais.append(hino)
        return hinos_finais

    async def sugerir_playlist_culto(
        self, tema_prompt: str, num_hinos: int = 6
    ) -> dict[str, Any]:
        """
        Analisa a intenção pastoral do usuário e sugere uma lista de hinos harmoniosa
        organizada por blocos litúrgicos de um culto.

        Args:
            tema_prompt: Tema pastoral descrito pelo usuário.
            num_hinos: Quantidade de hinos desejada (4-10).
        """
        num_hinos = max(4, min(10, num_hinos))

        if not tema_prompt or not tema_prompt.strip():
            return await self._gerar_playlist_padrao(num_hinos)

        palavras_relevantes = self._extrair_palavras_chave(tema_prompt)
        candidatos_ids = await self._buscar_candidatos_ids(
            palavras_relevantes, num_hinos
        )
        hinos_completos = await self._get_hinos_completos()
        temas_por_hino = await self._carregar_temas_candidatos(candidatos_ids)

        hinos_finais = self._selecionar_melhores_candidatos(
            candidatos_ids,
            hinos_completos,
            temas_por_hino,
            palavras_relevantes,
            num_hinos,
        )

        return self._estruturar_blocos(tema_prompt.strip(), hinos_finais)

    def _estruturar_blocos(self, tema: str, hinos: list[Hino]) -> dict[str, Any]:
        """Estrutura a lista de hinos selecionados em blocos litúrgicos de um culto."""
        blocos = []
        for i, hino in enumerate(hinos):
            nome_bloco = (
                NOMES_BLOCOS_LITURGICOS[i]
                if i < len(NOMES_BLOCOS_LITURGICOS)
                else f"{i+1}. Momento Especial"
            )
            blocos.append(
                {
                    "bloco": nome_bloco,
                    "hino": hino,
                }
            )

        return {
            "tema": tema,
            "hinos": hinos,
            "blocos": blocos,
        }
