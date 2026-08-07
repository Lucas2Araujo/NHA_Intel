import re
import asyncio
from typing import List, Dict, Any, Optional
from src.repositories.hino_repository import HinoRepository
from src.models.hino import Hino


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
        """Carrega e cacheia todos os hinos com campos completos para scoring."""
        if self._hinos_completos_cache is None:
            all_hinos = await self.hino_repository.get_all()
            self._hinos_completos_cache = {}
            for h in all_hinos:
                if h.id is not None:
                    # Carrega hino completo (com categoria, subcategoria, texto_base)
                    hino_completo = await self.hino_repository.get_by_id(h.id)
                    if hino_completo:
                        self._hinos_completos_cache[h.id] = hino_completo
        return self._hinos_completos_cache

    async def _get_temas_por_hino(self, hino_id: int) -> List[str]:
        """Retorna os temas associados a um hino via tabela de junção."""
        metadados = await self.hino_repository.get_metadados_relacionados(hino_id)
        return metadados.get("temas", [])

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
            # Se o tema estiver vazio, retorna seleção padrão de adoração
            hinos = await self.hino_repository.search("Santo")
            hinos_selecionados = (
                hinos[:num_hinos]
                if len(hinos) >= num_hinos
                else await self.hino_repository.get_all()
            )
            return self._estruturar_blocos(
                "Culto Geral", hinos_selecionados[:num_hinos], num_hinos
            )

        prompt_clean = tema_prompt.strip().lower()
        palavras_chave = re.findall(r"\w+", prompt_clean)
        palavras_relevantes = [p for p in palavras_chave if len(p) > 2]

        # Busca candidatos no repositório por relevância
        candidatos_ids: List[int] = []
        for kw in palavras_relevantes:
            resultados = await self.hino_repository.search(kw)
            for h in resultados:
                if h.id is not None and h.id not in candidatos_ids:
                    candidatos_ids.append(h.id)

        # Complementa com hinos principais se poucos candidatos
        if len(candidatos_ids) < num_hinos:
            todos = await self.hino_repository.get_all()
            for h in todos:
                if h.id is not None and h.id not in candidatos_ids:
                    candidatos_ids.append(h.id)
                if len(candidatos_ids) >= num_hinos * 3:
                    break

        # Carrega hinos completos para scoring adequado
        hinos_completos = await self._get_hinos_completos()

        # Busca temas associados para os candidatos (batch)
        temas_por_hino: Dict[int, List[str]] = {}
        for hino_id in candidatos_ids[:30]:  # Limita para não sobrecarregar
            temas_por_hino[hino_id] = await self._get_temas_por_hino(hino_id)

        # Pontuação semântica de relevância melhorada
        def _score(hino_id: int) -> int:
            hino = hinos_completos.get(hino_id)
            if not hino:
                return 0

            score = 0
            titulo_lower = hino.titulo.lower()
            texto = f"{titulo_lower} {hino.categoria or ''} {hino.subcategoria or ''} {hino.texto_base or ''}".lower()

            # Temas do banco de dados (tabela tema)
            temas_hino = [t.lower() for t in temas_por_hino.get(hino_id, [])]
            temas_texto = " ".join(temas_hino)

            for kw in palavras_relevantes:
                if kw in titulo_lower:
                    score += 5  # Match no título = alta relevância
                if kw in (hino.categoria or "").lower():
                    score += 3  # Match na categoria
                if kw in (hino.subcategoria or "").lower():
                    score += 3  # Match na subcategoria
                if kw in (hino.texto_base or "").lower():
                    score += 2  # Match no texto base
                if kw in temas_texto:
                    score += 4  # Match nos temas = muito relevante

            return score

        # Ordena candidatos por score e seleciona os melhores
        candidatos_ids.sort(key=_score, reverse=True)
        hinos_finais_ids = candidatos_ids[:num_hinos]

        # Converte IDs para objetos Hino
        hinos_finais = []
        for hid in hinos_finais_ids:
            hino = hinos_completos.get(hid)
            if hino:
                hinos_finais.append(hino)

        return self._estruturar_blocos(tema_prompt.strip(), hinos_finais, num_hinos)

    def _estruturar_blocos(
        self, tema: str, hinos: List[Hino], num_hinos: int = 6
    ) -> Dict[str, Any]:
        """Estrutura a lista de hinos selecionados em blocos litúrgicos de um culto."""
        # Blocos litúrgicos expandíveis conforme a quantidade de hinos
        nomes_blocos = [
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

        blocos = []
        for i, hino in enumerate(hinos):
            nome_bloco = (
                nomes_blocos[i] if i < len(nomes_blocos) else f"{i+1}. Momento Especial"
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
