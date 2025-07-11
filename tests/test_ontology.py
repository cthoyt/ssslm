"""Test writing OWL."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from curies import NamedReference
from curies.vocabulary import charlie

from ssslm import LiteralMapping
from ssslm.ontology import PREAMBLE, Metadata, write_owl_ttl


class TestOWL(unittest.TestCase):
    """Test writing OWL."""

    def test_metadata(self) -> None:
        """Test metadata object."""
        m = Metadata(uri="https://example.org/test.owl")
        self.assertEqual("<https://example.org/test.owl> a owl:Ontology .", m._rdf_str())

        m = Metadata(uri="https://example.org/test.owl", title="Test")
        self.assertEqual(
            "<https://example.org/test.owl> a owl:Ontology ;"
            '\n    dcterms:title "Test"^^xsd:string .',
            m._rdf_str(),
        )

        m = Metadata(uri="https://example.org/test.owl", title="Test", description="Description")
        self.assertEqual(
            "<https://example.org/test.owl> a owl:Ontology ;"
            '\n    dcterms:title "Test"^^xsd:string ;'
            '\n    dcterms:description "Description"^^xsd:string .',
            m._rdf_str(),
        )

    def test_write_owl_rdf(self) -> None:
        """Test writing OWL RDF."""
        mappings = [
            LiteralMapping(reference=NamedReference.from_curie("a:1", name="A"), text="a"),
            LiteralMapping(
                reference=NamedReference.from_curie("a:1", name="A"),
                text="a-syn",
                contributor=charlie,
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.owl")
            write_owl_ttl(mappings, path, prefix_map={"a": "https://example.org/a#"})

            self.assertEqual(
                dedent("""\
                    @prefix a: <https://example.org/a#> .
                    @prefix BFO: <http://purl.obolibrary.org/obo/BFO_> .
                    @prefix dcterms: <http://purl.org/dc/terms/> .
                    @prefix NCBITaxon: <http://purl.obolibrary.org/obo/NCBITaxon_> .
                    @prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .
                    @prefix OMO: <http://purl.obolibrary.org/obo/OMO_> .
                    @prefix orcid: <https://orcid.org/> .
                    @prefix owl: <http://www.w3.org/2002/07/owl#> .
                    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .

                """)
                + PREAMBLE
                + dedent("""\


                    a:1 a owl:Class ;
                        oboInOwl:hasRelatedSynonym "a" ;
                        oboInOwl:hasRelatedSynonym "a-syn" ;
                        rdfs:label "A" .

                    [
                        a owl:Axiom ;
                        owl:annotatedSource a:1 ;
                        owl:annotatedProperty oboInOwl:hasRelatedSynonym ;
                        owl:annotatedTarget "a-syn" ;
                        dcterms:contributor orcid:0000-0003-4423-4370 .
                    ] .

                    orcid:0000-0003-4423-4370 a NCBITaxon:9606 ; rdfs:label \
"Charles Tapley Hoyt"@en .
                """),
                path.read_text(),
            )
