import json
from dataclasses import dataclass


@dataclass(frozen=True)
class BlocoDiff:
    """Representa um bloco individual no diff de um hino."""

    tipo: str  # "igual", "modificado", "adicionado", "removido"
    texto: str | None = None
    antigo: list[str] | None = None
    novo: list[str] | None = None


@dataclass(frozen=True)
class EstatisticasDiff:
    """Estatísticas consolidadas de contagem de linhas alteradas."""

    linhas_adicionadas: int = 0
    linhas_removidas: int = 0
    linhas_alteradas: int = 0
    linhas_iguais: int = 0


def _normalize_string_list(val: object | None) -> list[str] | None:
    """Normaliza um valor para lista de strings ou None se nulo."""
    if val is None:
        return None
    if isinstance(val, list):
        return [str(item) for item in val]
    return [str(val)]


@dataclass(frozen=True)
class HinoComparativo:
    """
    Data Transfer Object (DTO) estritamente imutável representando
    a entidade de Comparação entre Hinário Novo e Antigo.
    """

    id: int | None
    numero_novo: str | None
    numero_antigo: str | None
    titulo_novo: str | None
    titulo_antigo: str | None
    categoria_nova: str | None = None
    categoria_antiga: str | None = None
    status_comparacao: str = (
        ""  # 'IDENTICO', 'MODIFICADO', 'NOVO_INEDITO', 'ANTIGO_DESCONTINUADO'
    )
    modificado: int = 0
    similaridade_pct: float = 0.0
    diff_texto: str | None = None
    diff_json: str | None = None
    resumo_alteracoes: str | None = None
    metodo_cruzamento: str | None = None

    def get_parsed_diff(self) -> tuple[EstatisticasDiff | None, list[BlocoDiff]]:
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
            blocos: list[BlocoDiff] = []
            for b in blocos_raw:
                tipo = b.get("tipo", "igual")
                texto = b.get("texto")
                antigo = b.get("antigo")
                novo = b.get("novo")

                antigo_list = _normalize_string_list(antigo)
                novo_list = _normalize_string_list(novo)

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
