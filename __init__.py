r"""
anatomia - deteccao de conteudo sensivel por ESTRUTURA CORPORAL.

Projeto satelite do Acervo. Nao classifica pigmento: localiza anatomia.
Nao decide: mede. Nao roda sobre foto de crianca: o portao veta antes.

    from anatomia import Avaliador, Portao, Detector

    av = Avaliador(portao=Portao.do_acervo(cfg))
    medida, candidato = av.avaliar_e_julgar(registro)

'Detector' e' exportado para teste e para o experimento; em producao use
sempre 'Avaliador', que poe o portao na frente. Ver avaliador.py.
"""

from .avaliador import POLITICA_PADRAO, Avaliador
from .detector import Detector
from .portao import LIMIAR_VETO_PADRAO, Portao
from .tipos import Candidato, Medida, Regiao

__all__ = ["Avaliador", "Portao", "Detector", "Medida", "Regiao", "Candidato",
           "POLITICA_PADRAO", "LIMIAR_VETO_PADRAO"]
__version__ = "0.1.0-desenho"
