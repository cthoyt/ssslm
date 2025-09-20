"""Tests for ScispaCy."""

import importlib.util
import unittest

from ssslm.ner import SpacyGrounder
from tests import cases


class ScispaCyTestCase(cases.BaseNERTestCase):
    """Test scispacy."""

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ["spacy", "scispacy", "en_core_sci_sm"]),
        reason="Need spacy and scispacy installed to run SpaCy tests",
    )
    def test_spacy(self) -> None:
        """Test spacy NER."""
        import spacy

        spacy_model = spacy.load("en_core_sci_sm")

        grounder = SpacyGrounder(
            matcher=cases.MockMatcher(),
            spacy_model=spacy_model,
        )
        self.assert_ner_alzheimer(grounder)
