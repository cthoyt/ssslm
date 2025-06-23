"""Generate OWL from the literal mappings."""

from __future__ import annotations

from collections import ChainMap
from pathlib import Path
from textwrap import dedent
from typing import Annotated, TextIO, Iterable

from curies import Reference
from ssslm import LiteralMapping, group_literal_mappings, get_prefixes
from typing_extensions import Doc

from pydantic import BaseModel, Field
from pystow.utils import safe_open


__all__ = [
    "Metadata",
    "write_owl_rdf",
    "DEFAULT_PREFIXES",
]
class Metadata(BaseModel):
    """Metadata for the ontology."""

    uri: str
    title: str | None = None
    description: str | None = None
    license: str | None = None
    comments: list[str] = Field(default_factory=list)

    def _rdf_str(self) -> str:
        pass


METADATA = f"""\
<{URI}> a owl:Ontology ;
    dcterms:title "Biosynonyms in OWL" ;
    dcterms:description "An ontology representation of community curated synonyms in Biosynonyms" ;
    dcterms:license <https://creativecommons.org/publicdomain/zero/1.0/> ;
    rdfs:comment "Built by https://github.com/biopragmatics/biosynonyms"^^xsd:string .
"""

PREAMBLE = """\
rdfs:label   a owl:AnnotationProperty; rdfs:label "label"^^xsd:string .
rdfs:seeAlso a owl:AnnotationProperty; rdfs:label "see also"^^xsd:string .
rdfs:comment a owl:AnnotationProperty; rdfs:label "comment"^^xsd:string .

oboInOwl:hasSynonym a owl:AnnotationProperty;
    rdfs:label "has synonym"^^xsd:string .

oboInOwl:hasExactSynonym a owl:AnnotationProperty;
    rdfs:label "has exact synonym"^^xsd:string .

oboInOwl:hasNarrowSynonym a owl:AnnotationProperty;
    rdfs:label "has narrow synonym"^^xsd:string .

oboInOwl:hasBroadSynonym a owl:AnnotationProperty;
    rdfs:label "has broad synonym"^^xsd:string .

oboInOwl:hasRelatedSynonym a owl:AnnotationProperty;
    rdfs:label "has related synonym"^^xsd:string .

oboInOwl:hasSynonymType a owl:AnnotationProperty;
    rdfs:label "has synonym type"^^xsd:string .

oboInOwl:hasDbXref a owl:AnnotationProperty;
    rdfs:label "has database cross-reference"^^xsd:string .

skos:exactMatch a owl:AnnotationProperty; rdfs:label "exact match"^^xsd:string .

dcterms:contributor a owl:AnnotationProperty; rdfs:label "contributor"^^xsd:string .
dcterms:source      a owl:AnnotationProperty; rdfs:label "source"^^xsd:string .
dcterms:license     a owl:AnnotationProperty; rdfs:label "license"^^xsd:string .
dcterms:description a owl:AnnotationProperty; rdfs:label "description"^^xsd:string .

BFO:0000051 a owl:ObjectProperty; rdfs:label "has part"^^xsd:string .

NCBITaxon:9606 a owl:Class ;
    rdfs:label "Homo sapiens" .

orcid:0000-0003-4423-4370 a NCBITaxon:9606 ;
    rdfs:label "Charles Tapley Hoyt"@en .

orcid:0000-0001-9439-5346 a NCBITaxon:9606 ;
    rdfs:label "Benjamin M. Gyori"@en .

# See new OMO synonyms at
# https://github.com/information-artifact-ontology/ontology-metadata/blob/master/src/templates/annotation_properties.tsv

OMO:0003000 a owl:AnnotationProperty;
    rdfs:label "abbreviation"^^xsd:string .

OMO:0003001 a owl:AnnotationProperty;
    rdfs:label "ambiguous synonym"^^xsd:string .

OMO:0003002 a owl:AnnotationProperty;
    rdfs:label "dubious synonym"^^xsd:string .

OMO:0003003 a owl:AnnotationProperty;
    rdfs:label "layperson synonym"^^xsd:string .

OMO:0003004 a owl:AnnotationProperty;
    rdfs:label "plural form"^^xsd:string .

OMO:0003005 a owl:AnnotationProperty;
    rdfs:label "UK spelling"^^xsd:string .

OMO:0003006 a owl:AnnotationProperty;
    rdfs:label "misspelling"^^xsd:string .

OMO:0003007 a owl:AnnotationProperty;
    rdfs:label "misnomer"^^xsd:string .

OMO:0003008 a owl:AnnotationProperty;
    rdfs:label "previous name"^^xsd:string .

OMO:0003009 a owl:AnnotationProperty;
    rdfs:label "legal name"^^xsd:string .

OMO:0003010 a owl:AnnotationProperty;
    rdfs:label "International Nonproprietary Name"^^xsd:string .

OMO:0003011 a owl:AnnotationProperty;
    rdfs:label "latin term"^^xsd:string .

OMO:0003012 a owl:AnnotationProperty;
    rdfs:label "acronym"^^xsd:string .
"""


def _text_for_turtle(literal_mapping: LiteralMapping) -> str:
    """Get the text ready for an object slot in Turtle, with optional language tag."""
    tt = f'"{_clean_str(literal_mapping.text)}"'
    if literal_mapping.language:
        tt += f"@{literal_mapping.language}"
    return tt


#: A default prefix map for SSSLM
DEFAULT_PREFIXES: dict[str, str] = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dcterms": "http://purl.org/dc/terms/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "oboInOwl": "http://www.geneontology.org/formats/oboInOwl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "orcid": "https://orcid.org/",
    "OMO": "http://purl.obolibrary.org/obo/OMO_",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "BFO": "http://purl.obolibrary.org/obo/BFO_",
}


def _write_prefix_map(
    prefixes: set[str], file: TextIO, *, prefix_map: dict[str, str] | None = None
) -> None:
    """Write the prefix map to the top of a turtle file."""
    for prefix, uri_prefix in _iter_prefix_map(prefixes, prefix_map=prefix_map):
        file.write(f"@prefix {prefix}: <{uri_prefix}> .\n")


def _iter_prefix_map(
    prefixes: set[str],
    *,
    prefix_map: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Generate a prefix map."""
    looked_up_prefix_map: dict[str, str] = {}
    for prefix in prefixes:
        if prefix_map and prefix in prefix_map:
            pass  # given explicitly, no need to look up in bioregistry
        elif prefix not in looked_up_prefix_map:
            import bioregistry

            resource = bioregistry.get_resource(prefix, strict=True)
            uri_prefix = resource.rdf_uri_format or resource.get_uri_prefix()
            if uri_prefix is None:
                raise ValueError(
                    f"Prefix has no URI expansion in Bioregistry: "
                    f"{prefix} ({bioregistry.get_name(prefix, strict=True)})"
                )
            looked_up_prefix_map[prefix] = uri_prefix

    chained_prefix_map = ChainMap(DEFAULT_PREFIXES, looked_up_prefix_map, prefix_map or {})
    return sorted(chained_prefix_map.items(), key=lambda i: i[0].casefold())


def _get_axiom_str(reference: Reference, literal_mapping: LiteralMapping) -> str | None:
    """Get the axiom string for a synonym."""
    axiom_parts = []
    if literal_mapping.contributor:
        axiom_parts.append(f"dcterms:contributor {literal_mapping.contributor.curie}")
    if literal_mapping.date:
        axiom_parts.append(f'dcterms:date "{literal_mapping.date_str}"^^xsd:date')
    if literal_mapping.source:
        axiom_parts.append(f'dcterms:source "{_clean_str(literal_mapping.source)}"')
    if literal_mapping.type:
        axiom_parts.append(f"oboInOwl:hasSynonymType {literal_mapping.type.curie}")
    for rr in literal_mapping.provenance:
        axiom_parts.append(f"oboInOwl:hasDbXref {rr.curie}")
    if literal_mapping.comment:
        axiom_parts.append(f'rdfs:comment "{_clean_str(literal_mapping.comment)}"')

    if not axiom_parts:
        # if there's no additional context to add, then we don't need to make an axiom
        return None

    axiom_parts_str = " ;\n".join(f"    {ax}" for ax in axiom_parts) + " ."
    axiom = f"""\
[
    a owl:Axiom ;
    owl:annotatedSource {reference.curie} ;
    owl:annotatedProperty {literal_mapping.predicate.curie} ;
    owl:annotatedTarget {_text_for_turtle(literal_mapping)} ;
{axiom_parts_str}
] .
"""
    return axiom


def write_owl_rdf(  # noqa:C901
    literal_mappings: Iterable[LiteralMapping],
    path: str | Path,
    *,
    prefix_definitions: Annotated[
        bool, Doc("Should the @prefix definitions be added at the top?")
    ] = True,
    class_definitions: Annotated[bool, Doc("Should the `a owl:Class` and label be added?")] = True,
    metadata: Metadata | None = None,
    prefix_map: dict[str, str] | None = None,
) -> None:
    dd = group_literal_mappings(literal_mappings)
    with safe_open(path, operation="write") as file:
        if prefix_definitions:
            _write_prefix_map(get_prefixes(dd), file=file, prefix_map=prefix_map)

        if metadata:
            file.write(f"\n{metadata._rdf_str()}\n")

        file.write(f"\n{PREAMBLE}\n")

        for reference, literal_mappings in dd.items():
            mains: list[str] = []
            axiom_strs: list[str] = []
            for literal_mapping in literal_mappings:
                mains.append(f"{literal_mapping.predicate.curie} {_text_for_turtle(literal_mapping)}")
                if axiom_str := _get_axiom_str(reference, literal_mapping):
                    axiom_strs.append(axiom_str)

            if class_definitions:
                file.write(f"\n{reference.curie} a owl:Class ;\n")
                if reference.name:
                    mains.append(f'rdfs:label "{_clean_str(reference.name)}"')
                else:
                    try:
                        name = next(synonym.name for synonym in literal_mappings if synonym.name)
                    except StopIteration:
                        pass  # could not extract a name, no worries!
                    else:
                        mains.append(f'rdfs:label "{_clean_str(name)}"')
            else:
                file.write(f"\n{reference.curie} ")

            file.write(" ;\n".join(f"    {m}" for m in mains) + " .\n")
            if axiom_strs:
                file.write("\n")
            for axiom_str in axiom_strs:
                file.write(dedent(axiom_str))


def _clean_str(s: str) -> str:
    return s
