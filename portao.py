r"""
==========================================================================
 anatomia.portao - a separacao estrutural que protege crianca
==========================================================================

O QUE E'

  Um VETO que roda ANTES do detector. Se o portao veta, nenhuma medida e'
  calculada - nao existe caminho no codigo em que o detector veja uma
  imagem vetada. A protecao nao e' um julgamento do detector; e' a ordem
  das operacoes.

FALHA FECHADA

  Toda duvida veta. Sinal ausente veta. Portao indisponivel veta TUDO - a
  categoria simplesmente nao produz candidatos naquele acervo.

  E' o oposto do padrao usual (na duvida, medir e deixar o limiar
  resolver). Aqui a duvida e' resolvida contra a medida, porque os dois
  erros nao custam a mesma coisa: nao marcar uma foto adulta e' um
  incomodo; medir a foto do banho da filha e' o dano que o projeto inteiro
  existe para evitar.

O PROBLEMA HONESTO DESTE PORTAO

  Ele se apoia em reconhecimento facial, e reconhecimento facial de bebe
  e' o sinal mais fraco do acervo - medido no projeto principal: uma foto
  de bebe casou com uma adulta sem parentesco a 0.46 de similaridade.

  Consequencias que o desenho assume em vez de esconder:

    1. O limiar de VETO e' mais BAIXO que o de identificacao (0.30 contra
       0.55). Aqui um falso positivo do reconhecimento nao custa quase
       nada - so' deixa de avaliar uma foto. Recall e' tudo; precisao nao
       importa.

    2. Crianca de costas, de longe, ou sem rosto visivel NAO e' pega por
       semelhanca. Por isso existe o modo ESTRITO, e por isso o
       experimento mede o RISCO RESIDUAL: quantas fotos de crianca o
       portao deixa passar.

    3. O portao nunca e' declarado "seguro" por argumento. Ele e' medido
       contra um conjunto de fotos de crianca rotulado a mao, e o numero
       que vale e' o RECALL DO PORTAO, nao a precisao do detector.

MODOS

  estrito : so' avalia imagem em que TODO rosto detectado casa com uma
            referencia adulta. Rosto desconhecido veta.
            Custo: num acervo com muita gente desconhecida, a categoria
            quase nao produz candidato. Beneficio: crianca desconhecida
            (visita, escola, praia) tambem fica protegida.

  padrao  : veta por semelhanca com pessoa protegida e por ausencia de
            sinal. Rosto adulto desconhecido passa.

  Qual usar nao se decide aqui: medem-se os dois no mesmo conjunto e
  olha-se a tabela. Ver EXPERIMENTO.md, experimento 0.
==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass


# Limiar de VETO. Deliberadamente abaixo de 'rostos.limiar_protecao' (0.40)
# do Acervo: aquele limiar decide "esta foto e' de alguem da familia", uma
# afirmacao. Este decide "pode ser", uma duvida - e duvida veta.
# NAO E' UM NUMERO MEDIDO. E' ponto de partida conservador; o experimento 0
# existe para substitui-lo por um numero medido.
LIMIAR_VETO_PADRAO = 0.30


@dataclass
class Portao:
    """Decide se uma imagem PODE ser medida. Nunca mede nada."""

    limiar_veto: float = LIMIAR_VETO_PADRAO
    modo: str = "padrao"              # 'padrao' | 'estrito'
    disponivel: bool = False          # falha fechada ate' prova em contrario
    motivo_indisponivel: str = "portao_nao_configurado"

    # -- construcao a partir da config do Acervo --------------------
    @classmethod
    def do_acervo(cls, cfg, refs_protegidas_carregadas: bool | None = None):
        """Le a config do Acervo e decide se o portao pode operar.

        Tres condicoes, todas necessarias:
          - rostos.ativo         : ha' deteccao de rosto no indice
          - rostos.identificar   : ha' reconhecimento (senao sim_protegido
                                   e' sempre None e o veto nao funciona)
          - rostos.nunca_avaliar : ha' pelo menos uma pessoa protegida
                                   declarada, com pasta de referencia

        Faltando qualquer uma, o portao fica indisponivel e a categoria
        inteira e' desligada. Nao existe modo degradado."""
        p = cls(limiar_veto=float(cfg.get("politicas.sensivel.limiar_veto",
                                          LIMIAR_VETO_PADRAO)),
                modo=str(cfg.get("politicas.sensivel.portao", "padrao")))
        protegidas = list(cfg.get("rostos.nunca_avaliar", []) or [])
        if not cfg.get("rostos.ativo", True):
            p.motivo_indisponivel = "portao_sem_deteccao_de_rosto"
        elif not cfg.get("rostos.identificar", False):
            p.motivo_indisponivel = "portao_sem_reconhecimento"
        elif not protegidas:
            p.motivo_indisponivel = "portao_sem_pessoas_protegidas"
        elif refs_protegidas_carregadas is False:
            p.motivo_indisponivel = "portao_sem_vetores_de_referencia"
        else:
            p.disponivel = True
            p.motivo_indisponivel = ""
        return p

    # -- decisao ----------------------------------------------------
    def libera(self, reg: dict) -> tuple[bool, str]:
        """(pode_avaliar, motivo). 'reg' e' a linha do indice do Acervo.

        So' le sinais JA' calculados - nao abre a imagem. Barato de
        proposito: o portao roda sobre o acervo inteiro, o detector so'
        sobre o que sobrar."""
        if not self.disponivel:
            return False, self.motivo_indisponivel

        if reg.get("erro"):
            return False, "erro_de_leitura"

        # Sinal ausente = imagem nao indexada por completo. Falha fechada:
        # sem sinal de rosto nao ha' como saber quem esta' na foto.
        if reg.get("faces") is None:
            return False, "sem_sinal_de_rosto"
        if reg.get("sim_protegido") is None:
            return False, "sem_sinal_de_reconhecimento"

        if float(reg["sim_protegido"]) >= self.limiar_veto:
            return False, "pessoa_protegida"

        if self.modo == "estrito":
            # Exige que o rosto MENOS reconhecido da imagem ainda case com
            # alguma referencia adulta. Um unico rosto desconhecido veta.
            #
            # SINAL QUE AINDA NAO EXISTE no indice do Acervo: hoje o nucleo
            # guarda so' o MAXIMO das semelhancas (sim_in). O modo estrito
            # precisa do MINIMO por imagem - ver EXPERIMENTO.md, secao
            # "mudancas necessarias no nucleo". Enquanto nao existir, o modo
            # estrito veta tudo, que e' o lado certo de errar.
            pior = reg.get("sim_min_conhecido")
            if pior is None:
                return False, "modo_estrito_sem_sinal"
            if float(pior) < self.limiar_veto:
                return False, "rosto_nao_identificado"

        return True, "liberado"

    # -- propagacao por grupo ---------------------------------------
    @staticmethod
    def propaga_veto(grupos, vetados: set[str]) -> set[str]:
        """Se um membro do grupo de duplicatas e' vetado, o grupo inteiro e'.

        Sem isto o portao tem um furo: a mesma foto existe no acervo em
        duas copias - uma nitida, onde o rosto e' reconhecido, e uma
        pequena e borrada, onde nao e'. A copia borrada passa pelo portao,
        e a categoria recebe a mesma crianca que a copia nitida protegeu.

        'grupos' e' a saida de Motor.agrupar, traduzida para caminhos."""
        fora = set(vetados)
        for membros in grupos:
            if any(p in fora for p in membros):
                fora.update(membros)
        return fora
