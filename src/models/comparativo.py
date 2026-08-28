import json
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass(frozen=True)
class BlocoDiff:
    """Representa um bloco individual no diff de um hino."""
    tipo: str  # "igual", "modificado", "adicionado", "removido"
    texto: Optional[str] = None
    antigo: Optional[List[str]] = None
    novo: Optional[List[str]] = None


@dataclass(frozen=True)
class EstatisticasDiff:
    """Estatísticas consolidadas de contagem de linhas alteradas."""
    linhas_adicionadas: int = 0
    linhas_removidas: int = 0
    linhas_alteradas: int = 0
    linhas_iguais: int = 0


@dataclass(frozen=True)
class HinoComparativo:
    """
    Data Transfer Object (DTO) estritamente imutável representando
    a entidade de Comparação entre Hinário Novo e Antigo.
    """
    id: Optional[int]
    numero_novo: Optional[str]
    numero_antigo: Optional[str]
    titulo_novo: Optional[str]
    titulo_antigo: Optional[str]
    categoria_nova: Optional[str] = None
    categoria_antiga: Optional[str] = None
    status_comparacao: str = ""  # 'IDENTICO', 'MODIFICADO', 'NOVO_INEDITO', 'ANTIGO_DESCONTINUADO'
    modificado: int = 0
    similaridade_pct: float = 0.0
    diff_texto: Optional[str] = None
    diff_json: Optional[str] = None
    resumo_alteracoes: Optional[str] = None
    metodo_cruzamento: Optional[str] = None

    def get_parsed_diff(self) -> Tuple[Optional[EstatisticasDiff], List[BlocoDiff]]:
        """Desserializa com segurança o diff_json estruturado."""
        if not self.diff_json or not self.diff_json.strip():
            return None, []
        try:
            data = json.loads(self.diff_json)
            stats_raw = data.get("estatisticas") or {}
            stats = EstatisticasDiff(
                linhas_adicionadas=int(stats_raw.get("linhas_adicionadas", 0)),
                linhas_removidas=int(stats_raw.get("linhas_removidas", 0)),
                linhas_alteradas=int(stats_raw.get("linhas_alteradas", 0)),
                linhas_iguais=int(stats_raw.get("linhas_iguais", 0)),
            )

            blocos_raw = data.get("blocos") or []
            blocos: List[BlocoDiff] = []
            for b in blocos_raw:
                tipo = b.get("tipo", "igual")
                texto = b.get("texto")
                antigo = b.get("antigo")
                novo = b.get("novo")

                antigo_list = antigo if isinstance(antigo, list) else ([str(antigo)] if antigo is not None else None)
                novo_list = novo if isinstance(novo, list) else ([str(novo)] if novo is not None else None)

                blocos.append(
                    BlocoDiff(
                        tipo=tipo,
                        texto=str(texto) if texto is not None else None,
                        antigo=antigo_list,
                        novo=novo_list,
                    )
                )
            return stats, blocos
        except Exception:
            return None, []

