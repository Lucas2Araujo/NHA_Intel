from dataclasses import dataclass


@dataclass(frozen=True)
class Versiculo:
    """
    DTO imutável representando um versículo bíblico individual.
    """

    livro: str
    capitulo: int
    numero: int
    texto: str

    @property
    def versiculo(self) -> int:
        """Alias para manter compatibilidade com acessos legados."""
        return self.numero


@dataclass(frozen=True)
class PassagemBiblica:
    """
    DTO imutável representando uma passagem bíblica com um conjunto ordenado de versículos.
    """

    referencia: str
    livro: str
    capitulo: int
    versiculos: list[Versiculo]

    @property
    def texto_formatado(self) -> str:
        """Retorna o texto de todos os versículos formatado com numeração."""
        return "\n".join(f"{v.numero}. {v.texto}" for v in self.versiculos)
