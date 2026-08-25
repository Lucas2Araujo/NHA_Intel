import re
from typing import List, Dict, Any, Optional
from src.repositories.hino_repository import HinoRepository
from src.models.hino import Hino

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
        self._hinos_completos_cache: Optional[Dict[int, Hino]] = None

    async def _get_hinos_completos(self) -> Dict[int, Hino]:
        """Carrega e cacheia todos os hinos com campos completos para scoring em uma única consulta."""
        if self._hinos_completos_cache is None:
            if hasattr(self.hino_repository, "get_all_complete"):
                all_hinos = await self.hino_repository.get_all_complete()
                self._hinos_completos_cache = {h.id: h for h in all_hinos if h.id is not None}
            else:
                all_hinos = await self.hino_repository.get_all()
                self._hinos_completos_cache = {}
                for h in all_hinos:
                    if h.id is not None:
                        hino_completo = await self.hino_repository.get_by_id(h.id)
                        if hino_completo:
                            self._hinos_completos_cache[h.id] = hino_completo
        return self._hinos_completos_cache


    async def _get_temas_por_hino(self, hino_id: int) -> List[str]:
        """Retorna os temas associados a um hino via tabela de junção."""
        metadados = await self.hino_repository.get_metadados_relacionados(hino_id)
        return metadados.get("temas", [])

    def _extrair_palavras_chave(self, prompt: str) -> List[str]:
        """Extrai palavras-chave relevantes (>2 caracteres) do prompt."""
        prompt_clean = prompt.strip().lower()
        palavras = re.findall(r"\w+", prompt_clean)
        return [p for p in palavras if len(p) > 2]

    async def _gerar_playlist_padrao(self, num_hinos: int) -> Dict[str, Any]:
        """Gera uma playlist padrão de adoração quando o prompt estiver vazio."""
        hinos = await self.hino_repository.search("Santo")
        hinos_selecionados = (
            hinos[:num_hinos]
            if len(hinos) >= num_hinos
            else await self.hino_repository.get_all()
        )
        return self._estruturar_blocos("Culto Geral", hinos_selecionados[:num_hinos])

    async def _buscar_candidatos_ids(
        self, palavras_relevantes: List[str], num_hinos: int
    ) -> List[int]:
        """Busca IDs de hinos candidatos no repositório com base nas palavras-chave."""
        candidatos_ids: List[int] = []
        for kw in palavras_relevantes:
            resultados = await self.hino_repository.search(kw)
            for h in resultados:
                if h.id is not None and h.id not in candidatos_ids:
                    candidatos_ids.append(h.id)

        # Complementa com hinos adicionais se houver poucos candidatos
        if len(candidatos_ids) < num_hinos:
            todos = await self.hino_repository.get_all()
            for h in todos:
                if h.id is not None and h.id not in candidatos_ids:
                    candidatos_ids.append(h.id)
                if len(candidatos_ids) >= num_hinos * 3:
                    break

        return candidatos_ids

    async def _carregar_temas_candidatos(
        self, candidatos_ids: List[int]
    ) -> Dict[int, List[str]]:
        """Carrega os temas dos hinos candidatos."""
        temas_por_hino: Dict[int, List[str]] = {}
        for hino_id in candidatos_ids[:30]:
            temas_por_hino[hino_id] = await self._get_temas_por_hino(hino_id)
        return temas_por_hino

    def _calcular_score_hino(
        self,
        hino: Optional[Hino],
        temas_hino: List[str],
        palavras_relevantes: List[str],
    ) -> int:
        """Calcula a pontuação semântica de relevância de um hino."""
        if not hino:
            return 0

        score = 0
        titulo_lower = hino.titulo.lower()
        categoria_lower = (hino.categoria or "").lower()
        subcategoria_lower = (hino.subcategoria or "").lower()
        texto_base_lower = (hino.texto_base or "").lower()
        temas_texto = " ".join(t.lower() for t in temas_hino)

        for kw in palavras_relevantes:
            if kw in titulo_lower:
                score += 5  # Match no título = alta relevância
            if kw in categoria_lower:
                score += 3  # Match na categoria
            if kw in subcategoria_lower:
                score += 3  # Match na subcategoria
            if kw in texto_base_lower:
                score += 2  # Match no texto base
            if kw in temas_texto:
                score += 4  # Match nos temas = muito relevante

        return score

    def _selecionar_melhores_candidatos(
        self,
        candidatos_ids: List[int],
        hinos_completos: Dict[int, Hino],
        temas_por_hino: Dict[int, List[str]],
        palavras_relevantes: List[str],
        num_hinos: int,
    ) -> List[Hino]:
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
    ) -> Dict[str, Any]:
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
        candidatos_ids = await self._buscar_candidatos_ids(palavras_relevantes, num_hinos)
        hinos_completos = await self._get_hinos_completos()
        temas_por_hino = await self._carregar_temas_candidatos(candidatos_ids)

        hinos_finais = self._selecionar_melhores_candidatos(
            candidatos_ids, hinos_completos, temas_por_hino, palavras_relevantes, num_hinos
        )

        return self._estruturar_blocos(tema_prompt.strip(), hinos_finais)

    def _estruturar_blocos(
        self, tema: str, hinos: List[Hino]
    ) -> Dict[str, Any]:
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
