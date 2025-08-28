"""Read literal mappings from RDF."""

from collections import defaultdict
from typing import NamedTuple

import rdflib
from curies import NamableReference, Reference
from curies.vocabulary import has_label
from rdflib import RDFS, SKOS

from ssslm import LiteralMapping

__all__ = [
    "read_from_skos",
]

LABEL_PREDICATES = {
    RDFS.label: 0,
    SKOS.prefLabel: 1,
}
PRED_TO_REF = {
    RDFS.label: has_label,
    SKOS.prefLabel: Reference(prefix="skos", identifier="prefLabel"),
    SKOS.altLabel: Reference(prefix="skos", identifier="altLabel"),
}

BEST_NAME_QUERY = """\
    SELECT ?uri ?predicate ?name
    WHERE {
        VALUES ?predicate { skos:prefLabel rdfs:label }
        ?uri ?predicate ?name .
    }
"""

LM_QUERY = """\
    SELECT ?uri ?predicate ?name
    WHERE {
        VALUES ?predicate { skos:prefLabel rdfs:label skos:altLabel }
        ?uri ?predicate ?name .
    }
"""

GET_URI_PREFIX = """\
    SELECT ?uri_prefix
    WHERE {
        ?ontology a skos:ConceptScheme ;
                  vann:preferredNamespaceUri ?uri_prefix .
    }
    LIMIT 1
"""

GET_CURIE_PREFIX = """\
    SELECT ?curie_prefix
    WHERE {
        ?ontology a skos:ConceptScheme ;
                  vann:preferredNamespacePrefix ?curie_prefix .
    }
    LIMIT 1
"""


def _ensure_graph(x: str | rdflib.Graph) -> rdflib.Graph:
    if isinstance(x, rdflib.Graph):
        return x
    rv = rdflib.Graph()
    rv.parse(x)
    return rv


def _ensure_prefixes(
    graph: rdflib.Graph, curie_prefix: str | None = None, uri_prefix: str | None = None
) -> tuple[str, str]:
    if not curie_prefix:
        curie_prefix_res = list(graph.query(GET_CURIE_PREFIX))
        if not curie_prefix_res:
            raise ValueError(
                "no CURIE prefix given and none could be looked "
                "up using vann:preferredNamespacePrefix"
            )
        curie_prefix = str(curie_prefix_res[0][0])

    if not uri_prefix:
        uri_prefix_res = list(graph.query(GET_URI_PREFIX))
        if not uri_prefix_res:
            raise ValueError(
                "no URI prefix given and none could be looked up using vann:preferredNamespaceUri"
            )
        uri_prefix = str(uri_prefix_res[0][0])
    return curie_prefix, uri_prefix


class _LabelTuple(NamedTuple):
    """A tuple representing a language."""

    predicate: rdflib.URIRef
    language: str
    value: str


def _rank_label_tuple(label_tuple: _LabelTuple) -> tuple[int, int, str, str]:
    if label_tuple[1] == "en":
        language_priority = 0
    else:
        language_priority = 1
    return (
        LABEL_PREDICATES[label_tuple[0]],
        language_priority,
        label_tuple.language,
        label_tuple.value,
    )


def _get_names(graph: rdflib.Graph, uri_prefix: str) -> dict[str, str]:
    # Step 1, get the best possible label. Use a hierarchy of label types and languages
    names_dd: defaultdict[str, list[_LabelTuple]] = defaultdict(list)
    for uri, predicate, name in graph.query(BEST_NAME_QUERY):
        if not str(uri).startswith(uri_prefix):
            continue
        names_dd[uri.removeprefix(uri_prefix)].append(
            _LabelTuple(predicate, name._language, name._value)
        )

    names: dict[str, str] = {
        identifier: min(label_tuples, key=_rank_label_tuple).value
        for identifier, label_tuples in names_dd.items()
    }
    return names


def read_from_skos(
    graph: str | rdflib.Graph, curie_prefix: str | None = None, uri_prefix: str | None = None
) -> list[LiteralMapping]:
    """Read literal mappings from a SKOS vocabulary."""
    graph = _ensure_graph(graph)
    curie_prefix, uri_prefix = _ensure_prefixes(
        graph, curie_prefix=curie_prefix, uri_prefix=uri_prefix
    )

    names = _get_names(graph, uri_prefix)

    def _get_reference(uri_ref: rdflib.URIRef) -> NamableReference:
        identifier = uri_ref.removeprefix(uri_prefix)
        return NamableReference(
            prefix=curie_prefix,
            identifier=identifier,
            name=names.get(identifier),
        )

    rv = [
        LiteralMapping(
            reference=_get_reference(uri),
            text=str(value),
            language=value._language,
            predicate=PRED_TO_REF[predicate],
        )
        for uri, predicate, value in graph.query(LM_QUERY)
        if uri.startswith(uri_prefix)
    ]
    return rv
