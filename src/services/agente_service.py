import re
import asyncio
from typing import List, Dict, Any
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

    async def sugerir_playlist_culto(self, tema_prompt: str) -> Dict[str, Any]:
        """
        Analisa a intenção pastoral do usuário e sugere uma lista de hinos harmoniosa
        organizada por blocos litúrgicos de um culto.
        """
        if not tema_prompt or not tema_prompt.strip():
            # Se o tema estiver vazio, retorna seleção padrão de adoração
            hinos = await self.hino_repository.search("Santo")
            hinos_selecionados = (
                hinos[:4] if len(hinos) >= 4 else await self.hino_repository.get_all()
            )
            return self._estruturar_blocos("Culto Geral", hinos_selecionados[:4])

        prompt_clean = tema_prompt.strip().lower()
        palavras_chave = re.findall(r"\w+", prompt_clean)
        palavras_relevantes = [p for p in palavras_chave if len(p) > 2]

        # Busca candidatos no repositório por relevância
        candidatos: List[Hino] = []
        for kw in palavras_relevantes:
            resultados = await self.hino_repository.search(kw)
            for h in resultados:
                if h not in candidatos:
                    candidatos.append(h)

        # Se a busca por palavras-chave retornar poucos hinos, complementa com hinos principais
        if len(candidatos) < 4:
            todos = await self.hino_repository.get_all()
            for h in todos:
                if h not in candidatos:
                    candidatos.append(h)
                if len(candidatos) >= 10:
                    break

        # Pontuação semântica de relevância
        def _score(hino: Hino) -> int:
            score = 0
            texto = f"{hino.titulo} {hino.categoria or ''} {hino.subcategoria or ''} {hino.texto_base or ''}".lower()
            for kw in palavras_relevantes:
                if kw in hino.titulo.lower():
                    score += 5
                if kw in texto:
                    score += 2
            return score

        candidatos.sort(key=_score, reverse=True)
        hinos_finais = candidatos[:4] if len(candidatos) >= 4 else candidatos

        return self._estruturar_blocos(tema_prompt.strip(), hinos_finais)

    def _estruturar_blocos(self, tema: str, hinos: List[Hino]) -> Dict[str, Any]:
        """Estrutura a lista de hinos selecionados em 4 blocos litúrgicos clássicos de um culto."""
        nomes_blocos = [
            "1. Abertura & Adoração",
            "2. Oração & Comunhão",
            "3. Mensagem & Edificação",
            "4. Encerramento & Gratidão",
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
