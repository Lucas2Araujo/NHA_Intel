from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Hino:
    """
    Data Transfer Object (DTO) estritamente imutável representando a entidade Hino.
    Garante ausência de efeitos colaterais e otimiza o uso de memória no modelo assíncrono.
    """

    id: Optional[int]
    numero: str
    titulo: str
    letra: Optional[str] = None
    autor_letra: Optional[str] = None
    autor_musica: Optional[str] = None
    texto_base: Optional[str] = None
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None
    link_video: Optional[str] = None
    letra_json: Optional[str] = None
    autores: Optional[str] = None
