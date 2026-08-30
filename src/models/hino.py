from dataclasses import dataclass


@dataclass(frozen=True)
class Hino:
    """
    Data Transfer Object (DTO) estritamente imutável representando a entidade Hino.
    Garante ausência de efeitos colaterais e otimiza o uso de memória no modelo assíncrono.
    """

    id: int | None
    numero: str
    titulo: str
    letra: str | None = None
    autor_letra: str | None = None
    autor_musica: str | None = None
    texto_base: str | None = None
    categoria: str | None = None
    subcategoria: str | None = None
    link_video: str | None = None
    letra_json: str | None = None
    autores: str | None = None
