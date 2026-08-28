r"""
==========================================================================
 anatomia.tipos - o que a biblioteca devolve (e o que ela NUNCA devolve)
==========================================================================

A REGRA QUE DEFINE ESTES TIPOS

  Esta biblioteca devolve MEDIDA, nunca VEREDITO.

  Ela diz "ha uma regiao classificada como BUTTOCKS_EXPOSED com confianca
  0.71 ocupando 4% da imagem". Ela nao diz "esta imagem e' sensivel".
  Quem decide isso e' politica, mora em YAML no Acervo, e pode ser lida,
  discutida e trocada sem tocar em codigo.

  E' a mesma separacao SINAL / POLITICA do projeto principal, e aqui ela
  nao e' estetica: a lista de classes que "contam" como sensivel carrega
  um julgamento normativo (ver anatomia.avaliador.POLITICA_PADRAO). Se
  esse julgamento ficasse dentro do detector, ele viraria invisivel.

PORQUE 'Medida' TEM O CAMPO 'avaliado'

  Ausencia de regiao e ausencia de avaliacao sao coisas diferentes e
  precisam ser distinguiveis a jusante:

    avaliado=True,  regioes=()   -> o detector olhou e nao achou nada
    avaliado=False, regioes=()   -> o detector NAO olhou (portao vetou)

  Se as duas colapsassem em "sem regioes", uma foto protegida por portao
  ficaria indistinguivel de uma foto limpa, e o log deixaria de provar que
  a protecao aconteceu. A prova importa mais que o resultado.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Regiao:
    """Uma deteccao crua do modelo. Nada aqui e' interpretado.

    'classe' e' o rotulo CRU do detector, sem traducao e sem agrupamento.
    Traduzir aqui ("BUTTOCKS_EXPOSED" -> "nudez") esconderia a decisao
    dentro da biblioteca. O nome cru sobe ate' o YAML."""

    classe: str
    confianca: float
    caixa: tuple[int, int, int, int]   # x, y, largura, altura em pixels
    area_rel: float                    # area da caixa / area da imagem

    def como_dict(self) -> dict[str, Any]:
        return {"classe": self.classe, "confianca": round(self.confianca, 4),
                "caixa": list(self.caixa), "area_rel": round(self.area_rel, 5)}


@dataclass(frozen=True)
class Medida:
    """O que a biblioteca devolve por imagem.

    Guardar isto INTEIRO no indice e' deliberado: com as regioes cruas
    persistidas, varrer limiares depois custa zero GPU. E' o que permite
    escolher o ponto de operacao OLHANDO A CURVA em vez de chutar - o erro
    que ja' custou tres calibragens erradas no projeto principal."""

    avaliado: bool
    motivo: str                       # por que foi, ou por que nao foi
    regioes: tuple[Regiao, ...] = ()
    versao_modelo: str = ""
    ms: float = 0.0                   # tempo de inferencia, para orcamento

    @property
    def confianca_maxima(self) -> float:
        return max((r.confianca for r in self.regioes), default=0.0)

    def classes(self) -> set[str]:
        return {r.classe for r in self.regioes}

    def como_dict(self) -> dict[str, Any]:
        return {"avaliado": self.avaliado, "motivo": self.motivo,
                "versao_modelo": self.versao_modelo, "ms": round(self.ms, 2),
                "regioes": [r.como_dict() for r in self.regioes]}


@dataclass(frozen=True)
class Candidato:
    """A saida da POLITICA. Chama-se Candidato, nao Classificacao, porque
    a assimetria de custo esta' no nome do tipo: marcar de menos e' chato,
    marcar foto de familia e' grave. Nada aqui autoriza acao automatica."""

    e_candidato: bool
    motivo: str
    classes_que_dispararam: tuple[str, ...] = ()
    confianca: float = 0.0
    revisar_sempre: bool = True       # nao existe caminho que pule o humano


NAO_AVALIADO = Medida(avaliado=False, motivo="nao_avaliado")
