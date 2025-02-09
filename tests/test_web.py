"""Tests for the grounding web app."""

import unittest

from curies import NamableReference
from starlette.testclient import TestClient

from ssslm import Annotation, LiteralMapping, Match, make_grounder
from ssslm.web import get_app


class TestApp(unittest.TestCase):
    """Tests for the grounding web app."""

    def setUp(self) -> None:
        """Set up a test app."""
        literal_mappings = [
            LiteralMapping(
                reference=NamableReference(prefix="p1", identifier="i1", name="n1"),
                text="test",
            ),
            LiteralMapping(
                reference=NamableReference(prefix="p1", identifier="i2", name="n2"),
                text="nope",
            ),
        ]
        grounder = make_grounder(literal_mappings)
        self.app = get_app(grounder)
        self.client = TestClient(self.app)

    def test_ground(self) -> None:
        """Test grounding."""
        matches = [Match.model_validate(m) for m in self.client.get("/api/ground/Test").json()]
        self.assertEqual(1, len(matches))
        match = matches[0]
        self.assertEqual("p1", match.prefix)
        self.assertEqual("i1", match.identifier)

    def test_annotate(self) -> None:
        """Test annotate."""
        sentence = "This is a test sentence."
        res = self.client.post("/api/annotate", json={"text": sentence})

        annotations = [Annotation.model_validate(m) for m in res.json()]
        self.assertEqual(1, len(annotations))
        annotation = annotations[0]
        self.assertEqual("p1", annotation.prefix)
        self.assertEqual("i1", annotation.identifier)
        self.assertEqual(10, annotation.start)
