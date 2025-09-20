"""Tests for GLiNER."""

import importlib.util
import unittest

from ssslm.ner import GLiNERGrounder
from tests import cases


class GlinerTestCase(cases.BaseNERTestCase):
    """Test GLiNER."""

    @unittest.skipUnless(importlib.util.find_spec("gliner"), reason="Need GLiNER installed")
    def test_gliner(self) -> None:
        """Test GLiNER NER."""
        grounder = GLiNERGrounder(
            matcher=cases.MockMatcher(),
            labels=["disease"],
        )
        self.assert_ner_alzheimer(grounder)
