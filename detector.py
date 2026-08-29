r"""
anatomia.detector - NudeNet adapter, reduced to MEASUREMENT.

The one-line summaries below are in English, for anyone integrating this
library. The longer reasoning is in Portuguese, where it was written.

==========================================================================

PORQUE ANATOMIA E NAO COR

  A heuristica anterior media fracao de pele por faixa YCrCb. Foi
  implementada, medida em 540 imagens reais e descartada: precisao de ~7%,
  e - o motivo decisivo - as faixas YCrCb foram calibradas historicamente
  em amostras de pele clara. Nao e' problema de ajuste: nao existe faixa
  de cor justa.

  Um torso e' um torso em qualquer tom de pele. Localizar ESTRUTURA e'
  invariante a pigmento de um jeito que classificar cor nunca sera'.

O QUE ISSO NAO COMPRA

  Invariancia da GEOMETRIA nao e' invariancia do MODELO. O NudeNet e' um
  YOLO treinado em imagens coletadas da web, e detectores desse tipo tem
  desempenho desigual documentado entre tons de pele, tipos de corpo e
  condicoes de luz - nao porque medem cor, mas porque o conjunto de treino
  e' desbalanceado.

  A tese do projeto ("anatomia e' mais justa que cor") e' uma AFIRMACAO
  MEDIVEL, nao um teorema. O experimento 2 mede exatamente isso, em pares
  casados por conteudo (ver EXPERIMENTO.md). Ate' esse numero existir, a
  tese fica escrita como hipotese.

O QUE ESTE ADAPTADOR FAZ E NAO FAZ

  FAZ  : chama o detector, normaliza a saida para Region, mede o tempo,
         registra a versao do modelo em cada medida.
  NAO  : nao decide, nao filtra por confianca, nao agrupa rotulo, nao
         traduz rotulo. Tudo isso e' politica e sobe para o YAML.

  Nao filtrar por confianca aqui e' o que torna a varredura de limiar
  gratuita depois: as regioes cruas ficam gravadas, e mudar o ponto de
  operacao vira uma consulta SQL, nao uma nova passada de GPU.
==========================================================================
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from .types import Measurement, Region


@dataclass
class Detector:
    """Wraps NudeNet. Loads on demand - the module imports without it."""

    # 320n e' o padrao do NudeNet 3.4: onnxruntime, sem torch, roda em CPU
    # em dezenas de ms. Numa RTX 4050 de 6 GB o gargalo e' decodificar
    # JPEG, nao inferir - por isso a paralelizacao util e' de leitura.
    model: str = "nudenet-320n"
    _d: object = field(default=None, repr=False)

    def available(self) -> bool:
        try:
            import nudenet  # noqa: F401
            return True
        except ImportError:
            return False

    def load(self):
        if self._d is None:
            from nudenet import NudeDetector
            self._d = NudeDetector()
        return self._d

    def version(self) -> str:
        """Recorded in EVERY measurement.

        Sem isto, um numero medido hoje nao e' comparavel com o de amanha,
        e a tabela do experimento vira folclore."""
        try:
            import nudenet
            v = getattr(nudenet, "__version__", "?")
        except ImportError:
            v = "missing"
        return f"{self.model}@nudenet-{v}"

    # -- measurement ------------------------------------------------
    def measure(self, source,
                dimensions: tuple[int, int] | None = None) -> Measurement:
        """source: path, BGR ndarray or PIL.Image.

        'dimensions' e' (largura, altura) da imagem como o detector a ve';
        vem do indice para nao reabrir o arquivo so' para saber o tamanho.
        Sem ela, area_ratio fica 0.0 e a politica que depende de area nao
        dispara - falha fechada tambem aqui."""
        if not self.available():
            return Measurement(evaluated=False, reason="detector_missing")
        t0 = time.perf_counter()
        try:
            raw = self.load().detect(
                str(source) if isinstance(source, (str, Path)) else source)
        except Exception as e:
            return Measurement(evaluated=False, reason=f"detector_error: {e}",
                               model_version=self.version())
        ms = (time.perf_counter() - t0) * 1000.0

        area = float(dimensions[0] * dimensions[1]) if dimensions else 0.0
        regions = []
        for d in raw or []:
            x, y, w, h = (int(v) for v in d.get("box", (0, 0, 0, 0)))
            regions.append(Region(
                label=str(d.get("class", "?")),
                confidence=float(d.get("score", 0.0)),
                box=(x, y, w, h),
                area_ratio=(w * h / area) if area > 0 else 0.0))
        return Measurement(evaluated=True, reason="measured",
                           regions=tuple(regions),
                           model_version=self.version(), ms=ms)
