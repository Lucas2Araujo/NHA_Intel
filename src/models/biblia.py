from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Versiculo:
    """
    DTO imutável representando um versículo bíblico individual.
    """

    livro: str
    capitulo: int
    versiculo: int
    texto: str


@dataclass(frozen=True)
class PassagemBiblica:
    """
    DTO imutável representando uma passagem bíblica com um conjunto ordenado de versículos.
    """

    referencia: str
    livro: str
    capitulo: int
    versiculos: List[Versiculo]

    @property
    def texto_formatado(self) -> str:
        """Retorna o texto de todos os versículos formatado com numeração."""
        return "\n".join(f"{v.versiculo}. {v.texto}" for v in self.versiculos)
