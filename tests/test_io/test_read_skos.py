"""Tests for SKOS I/O."""

import unittest
from typing import ClassVar

import rdflib
from curies import NamableReference, Reference

from ssslm import LiteralMapping
from ssslm.io.skos import _ensure_graph, _ensure_prefixes, read_from_skos

TEST_URL = (
    "https://raw.githubusercontent.com/dini-ag-kim/schulfaecher/refs/heads/main/schulfaecher.ttl"
)

TEST_LITERAL_1 = LiteralMapping(
    text="MINT",
    language="de",
    reference=NamableReference(prefix="subj", identifier="s1019", name="MINT"),
    predicate=Reference(prefix="skos", identifier="prefLabel"),
)
TEST_LITERAL_2 = LiteralMapping(
    text="Chemie, Physik, Biologie",
    language="de",
    reference=NamableReference(prefix="subj", identifier="s1019", name="MINT"),
    predicate=Reference(prefix="skos", identifier="altLabel"),
)
TEST_LITERAL_3 = LiteralMapping(
    text="Naturwissenschaften",
    language="de",
    reference=NamableReference(prefix="subj", identifier="s1019", name="MINT"),
    predicate=Reference(prefix="skos", identifier="altLabel"),
)


class TestSKOS(unittest.TestCase):
    """Test reading SKOS."""

    graph: ClassVar[rdflib.Graph]

    @classmethod
    def setUpClass(cls) -> None:
        """Test up the test case."""
        cls.graph = _ensure_graph(TEST_URL)

    def test_ensure_prefixes(self) -> None:
        """Test extracting prefixes when none available."""
        self.assertEqual(
            ("subj", "https://w3id.org/kim/schulfaecher/"), _ensure_prefixes(self.graph)
        )

    def test_read_skos(self) -> None:
        """Test reading SKOS."""
        literal_mappings = read_from_skos(self.graph)
        self.assertNotEqual(0, len(literal_mappings), msg="no mappings extracted")
        self.assertIn(TEST_LITERAL_1, literal_mappings)
        self.assertIn(TEST_LITERAL_2, literal_mappings)
        self.assertIn(TEST_LITERAL_3, literal_mappings)
