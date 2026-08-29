r"""
anatomia - sensitive-content detection by BODY STRUCTURE, not skin tone.

It does not classify pigment: it locates anatomy. It does not decide: it
measures. It never runs on a photo of a child - the gate vetoes first.

    from anatomia import Evaluator, Gate, Detector

    ev = Evaluator(gate=Gate.from_config(cfg))
    measurement, candidate = ev.evaluate_and_judge(record)

'Detector' is exported for testing and for the experiment; in production
always use 'Evaluator', which puts the gate in front. See evaluator.py.

Documentation note: one-line summaries are in English. The longer design
reasoning, and EXPERIMENTO.md, are in Brazilian Portuguese - that is where
the thinking happened, and translating it would cost more than it buys.
"""

from .detector import Detector
from .evaluator import DEFAULT_POLICY, Evaluator
from .gate import DEFAULT_VETO_THRESHOLD, Gate
from .types import Candidate, Measurement, NOT_EVALUATED, Region

__all__ = ["Evaluator", "Gate", "Detector",
           "Measurement", "Region", "Candidate", "NOT_EVALUATED",
           "DEFAULT_POLICY", "DEFAULT_VETO_THRESHOLD"]
__version__ = "0.2.0-design"
