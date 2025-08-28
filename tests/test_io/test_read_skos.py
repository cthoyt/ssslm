"""Tests for SKOS I/O."""

import unittest
from typing import ClassVar

import rdflib
from curies import NamableReference, Reference

from ssslm import LiteralMapping
from ssslm.io.skos import _ensure_graph, _ensure_prefixes, _get_names, read_from_skos

TEST_URL = (
    "https://raw.githubusercontent.com/dini-ag-kim/schulfaecher/refs/heads/main/schulfaecher.ttl"
)
URI_PREFIX = "http://w3id.org/kim/schulfaecher/"

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

    def test_names(self) -> None:
        """Test getting names."""
        names = _get_names(self.graph, URI_PREFIX)
        self.assertNotEqual(0, len(names), msg="no names extracted")
        self.assertIn("s1000", names)
        self.assertEqual("Alt-Griechisch", names["s1000"])

    def test_names_constructed(self) -> None:
        """Test getting names from a constructed example."""
        ttl = """\
            @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            [] a skos:ConceptScheme .

            <http://w3id.org/kim/schulfaecher/s1000> a skos:Concept ;
                rdfs:label "Ancient Greek"@en ;
                skos:prefLabel "Alt-Griechisch"@de .

            <http://w3id.org/kim/schulfaecher/s1004> a skos:Concept ;
                skos:prefLabel "Performing Arts"@en , "Darstellendes Spiel"@de ;
                skos:altLabel "Theater"@de , "Theater"@en .

        """
        graph = rdflib.Graph()
        graph.parse(data=ttl, format="ttl")
        names = _get_names(graph, URI_PREFIX)
        self.assertNotEqual(0, len(names), msg="no names extracted")

        # test that rdfs:label is highest priority
        self.assertIn("s1000", names)
        self.assertEqual("Ancient Greek", names["s1000"])

        self.assertIn("s1004", names)
        self.assertEqual("Performing Arts", names["s1004"])

    def test_read_skos(self) -> None:
        """Test reading SKOS."""
        literal_mappings = read_from_skos(self.graph, uri_prefix=URI_PREFIX)
        self.assertNotEqual(0, len(literal_mappings), msg="no mappings extracted")
        self.assertIn(TEST_LITERAL_1, literal_mappings)
        self.assertIn(TEST_LITERAL_2, literal_mappings)
        self.assertIn(TEST_LITERAL_3, literal_mappings)
