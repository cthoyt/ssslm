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
STOP = 68
ALZ = NamedReference(prefix="MESH", identifier="D000544", name="Alzheimer Disease")
LM = LiteralMapping(
    reference=ALZ,
    text="alzheimer's disease",
)


REQUIRES_GILDA = unittest.skipUnless(GILDA_AVAILABLE, reason="gilda is required")


class MockMatcher(Matcher):
    """A mock matcher."""

    def get_matches(self, text: str, **kwargs: Any) -> list[Match]:
        """Get alzheimers match."""
        return [Match(reference=ALZ, score=1.0)]


class BaseNERTestCase(unittest.TestCase):
    """A test case with a shared test."""

    def assert_ner_alzheimer(self, grounder: Grounder) -> None:
        """Test grounding a sentence mentioning Alzheimer's disease."""
        annotations = grounder.annotate(
            "The APOE e4 mutation is correlated with risk for Alzheimer's disease."
        )
        annotation_index = {
            (annotation.match.reference, annotation.start, annotation.end)
            for annotation in annotations
        }
        self.assertIn(
            (ALZ, 49, 68),
            annotation_index,
        )
