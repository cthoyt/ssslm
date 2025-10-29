"""Test cases and constants."""

import unittest
from typing import Any

from curies import NamedReference

from ssslm import Grounder, LiteralMapping, Match, Matcher
from ssslm.model import GILDA_AVAILABLE

__all__ = [
    "REQUIRES_GILDA",
    "BaseNERTestCase",
    "MockMatcher",
]

TEXT = "The APOE e4 mutation is correlated with risk for Alzheimer's disease."
START = 49
STOP = 66
ALZHEIMER_REFERENCE = NamedReference(prefix="MESH", identifier="D000544", name="Alzheimer Disease")
LM_1 = LiteralMapping(
    reference=ALZHEIMER_REFERENCE,
    text="alzheimer disease",
)
LM_2 = LiteralMapping(
    reference=ALZHEIMER_REFERENCE,
    text="alzheimer's disease",
)
LM_3 = LiteralMapping(
    reference=ALZHEIMER_REFERENCE,
    text="Alzheimer's disease",
)


REQUIRES_GILDA = unittest.skipUnless(GILDA_AVAILABLE, reason="gilda is required")


class MockMatcher(Matcher):
    """A mock matcher."""

    def get_matches(self, text: str, **kwargs: Any) -> list[Match]:
        """Get alzheimers match."""
        return [Match(reference=ALZHEIMER_REFERENCE, score=1.0)]

    def not_empty(self) -> bool:
        """Return true."""
        return True


class BaseNERTestCase(unittest.TestCase):
    """A test case with a shared test."""

    def assert_ner_alzheimer(self, grounder: Grounder) -> None:
        """Test grounding a sentence mentioning Alzheimer's disease."""
        annotations = grounder.annotate(
            "The APOE e4 mutation is correlated with risk for Alzheimer disease."
        )
        annotation_index = {
            (annotation.match.reference, annotation.start, annotation.end)
            for annotation in annotations
        }
        self.assertIn(
            (ALZHEIMER_REFERENCE, START, STOP),
            annotation_index,
        )
