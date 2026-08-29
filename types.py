r"""
anatomia.types - what the library returns, and what it never returns.

The one-line summaries below are in English, for anyone integrating this
library. The longer reasoning is in Portuguese, where it was written.

==========================================================================

A REGRA QUE DEFINE ESTES TIPOS

  Esta biblioteca devolve MEDIDA, nunca VEREDITO.

  Ela diz "ha uma regiao classificada como BUTTOCKS_EXPOSED com confianca
  0.71 ocupando 4% da imagem". Ela nao diz "esta imagem e' sensivel".
  Quem decide isso e' politica, mora em YAML no consumidor, e pode ser
  lida, discutida e trocada sem tocar em codigo.

  E' a mesma separacao SINAL / POLITICA do projeto principal, e aqui ela
  nao e' estetica: a lista de rotulos que "contam" como sensivel carrega
  um julgamento normativo (ver anatomia.evaluator.DEFAULT_POLICY). Se
  esse julgamento ficasse dentro do detector, ele viraria invisivel.

PORQUE 'Measurement' TEM O CAMPO 'evaluated'

  Ausencia de regiao e ausencia de avaliacao sao coisas diferentes e
  precisam ser distinguiveis a jusante:

    evaluated=True,  regions=()   -> o detector olhou e nao achou nada
    evaluated=False, regions=()   -> o detector NAO olhou (o portao vetou)

  Se as duas colapsassem em "sem regioes", uma foto protegida pelo portao
  ficaria indistinguivel de uma foto limpa, e o log deixaria de provar que
  a protecao aconteceu. A prova importa mais que o resultado.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Region:
    """One raw detection. Nothing here is interpreted.

    'label' e' o rotulo CRU do detector, sem traducao e sem agrupamento.
    Traduzir aqui ("BUTTOCKS_EXPOSED" -> "nudez") esconderia a decisao
    dentro da biblioteca. O nome cru sobe ate' o YAML."""

    label: str
    confidence: float
    box: tuple[int, int, int, int]   # x, y, width, height in pixels
    area_ratio: float                # box area / image area

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label,
                "confidence": round(self.confidence, 4),
                "box": list(self.box),
                "area_ratio": round(self.area_ratio, 5)}


@dataclass(frozen=True)
class Measurement:
    """What the library returns per image.

    Guardar isto INTEIRO no indice e' deliberado: com as regioes cruas
    persistidas, varrer limiares depois custa zero GPU. E' o que permite
    escolher o ponto de operacao OLHANDO A CURVA em vez de chutar - o erro
    que ja' custou tres calibragens erradas no projeto principal."""

    evaluated: bool
    reason: str                          # why it ran, or why it did not
    regions: tuple[Region, ...] = ()
    model_version: str = ""
    ms: float = 0.0                      # inference time, for budgeting

    @property
    def max_confidence(self) -> float:
        return max((r.confidence for r in self.regions), default=0.0)

    def labels(self) -> set[str]:
        return {r.label for r in self.regions}

    def as_dict(self) -> dict[str, Any]:
        return {"evaluated": self.evaluated, "reason": self.reason,
                "model_version": self.model_version, "ms": round(self.ms, 2),
                "regions": [r.as_dict() for r in self.regions]}


@dataclass(frozen=True)
class Candidate:
    """The output of POLICY. Never authorises automatic action.

    Chama-se Candidate, nao Classification, porque a assimetria de custo
    esta' no nome do tipo: marcar de menos e' chato, marcar foto de
    familia e' grave."""

    is_candidate: bool
    reason: str
    triggered_labels: tuple[str, ...] = ()
    confidence: float = 0.0
    always_review: bool = True       # nao existe caminho que pule o humano


NOT_EVALUATED = Measurement(evaluated=False, reason="not_evaluated")
