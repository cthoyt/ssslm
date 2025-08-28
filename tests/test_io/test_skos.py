"""Tests for SKOS I/O."""

import unittest
from typing import ClassVar

import rdflib
from curies import NamableReference, Reference

from ssslm import LiteralMapping, read_skos
from ssslm.io.skos import _ensure_prefixes, _get_names

TEST_URL = (
    "https://raw.githubusercontent.com/dini-ag-kim/schulfaecher/refs/heads/main/schulfaecher.ttl"
)
TEST_TTL = """\
@base <http://w3id.org/kim/schulfaecher/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix oeh: <http://w3id.org/openeduhub/vocabs/discipline/> .
@prefix vann: <http://purl.org/vocab/vann/> .

<> a skos:ConceptScheme ;
    dct:title "Schulfächer"@de ;
    dct:description "Werteliste von Fächern im Schulbereich."@de ;
    dct:publisher "DINI-AG-KIM OER-Metadatengruppe"@de ;
    dct:created "2021-03-03"^^xsd:date ;
    dct:license <http://creativecommons.org/publicdomain/zero/1.0/> ;
    vann:preferredNamespaceUri "https://w3id.org/kim/schulfaecher/" ;
    vann:preferredNamespacePrefix "subj";
    skos:hasTopConcept <s1000>, <s1040>, <s1001>, <s1002>, <s1003>, <s1004>,
        <s1005>, <s1006>, <s1041>, <s1007>, <s1044>, <s1045>, <s1008>,
        <s1009>, <s1010>, <s1011>, <s1012>, <s1047>, <s1034>, <s1013>, <s1014>,
        <s1035>, <s1015>, <s1016>, <s1017>, <s1046>, <s1019>, <s1020>, <s1036>,
        <s1021>, <s1022>, <s1023>, <s1037>, <s1038>, <s1043>, <s1024>, <s1025>,
        <s1026>, <s1027>, <s1028>, <s1029>, <s1039>, <s1030>, <s1031>, <s1032>,
        <s1033> .

<s1000> a skos:Concept ;
    skos:prefLabel "Alt-Griechisch"@de ;
    skos:closeMatch oeh:20003 ;
    skos:topConceptOf <> .

<s1019> a skos:Concept ;
    skos:prefLabel "MINT"@de ;
    skos:altLabel "Chemie, Physik, Biologie"@de ;
    skos:altLabel "Naturwissenschaften"@de ;
    skos:related <s1001>, <s1002>, <s1013>, <s1017>, <s1022> ;
    skos:closeMatch oeh:04003 ;
    skos:topConceptOf <> .
"""
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
        cls.graph = rdflib.Graph()
        cls.graph.parse(data=TEST_TTL)

    def test_ensure_prefixes(self) -> None:
        """Test extracting prefixes when none available."""
        self.assertEqual(
            ("subj", "https://w3id.org/kim/schulfaecher/"), _ensure_prefixes(self.graph)
        )

    def test_names(self) -> None:
        """Test getting names."""
        names = _get_names(self.graph, URI_PREFIX)
        self.assertNotEqual(0, len(names), msg="no names extracted")
        self.assertIn("s1000", names, msg=f"Names: {names}")
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

        # test that rdfs:label is the highest priority
        self.assertIn("s1000", names)
        self.assertEqual("Ancient Greek", names["s1000"])

        self.assertIn("s1004", names)
        self.assertEqual("Performing Arts", names["s1004"])

    def test_read_skos(self) -> None:
        """Test reading SKOS."""
        literal_mappings = read_skos(self.graph, uri_prefix=URI_PREFIX)
        self.assertNotEqual(0, len(literal_mappings), msg="no mappings extracted")
        self.assertIn(TEST_LITERAL_1, literal_mappings)
        self.assertIn(TEST_LITERAL_2, literal_mappings)
        self.assertIn(TEST_LITERAL_3, literal_mappings)
