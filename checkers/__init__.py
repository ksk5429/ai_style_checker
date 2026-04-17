"""AI Style Checker — modular detection engine for academic manuscripts."""

from checkers.ai_patterns import AIPatternChecker
from checkers.burstiness import BurstinessChecker
from checkers.vocabulary import VocabularyChecker
from checkers.readability import ReadabilityChecker
from checkers.hedging import HedgingChecker
from checkers.passive_voice import PassiveVoiceChecker
from checkers.structure import StructureChecker
from checkers.repetition import RepetitionChecker
from checkers.claims import ClaimChecker

ALL_CHECKERS = [
    AIPatternChecker,
    BurstinessChecker,
    VocabularyChecker,
    ReadabilityChecker,
    HedgingChecker,
    PassiveVoiceChecker,
    StructureChecker,
    RepetitionChecker,
    ClaimChecker,
]

__all__ = ["ALL_CHECKERS"]
