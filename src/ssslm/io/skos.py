"""Read literal mappings from RDF."""

from collections import defaultdict
from typing import TypeAlias

import rdflib
from curies import NamableReference
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

BEST_NAME_QUERY = """\
    SELECT ?uri ?predicate ?name
    WHERE {
        VALUES ?predicate { skos:prefLabel rdfs:label }
        ?uri ?predicate ?name .
    }
"""

ALL_NAME_QUERY = """\
    SELECT ?uri ?name
    WHERE {
        ?uri skos:prefLabel|rdfs:label ?name .
    }
"""

SYNONYM_QUERY = """\
    SELECT ?uri ?synonym
    WHERE {
        ?uri skos:altLabel ?synonym .
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


PP: TypeAlias = tuple[rdflib.URIRef, str, str]


def _rank_pp(pp: PP):
    if pp[1] == "en":
        two = (0, "en")
    else:
        two = (1, pp[1])
    return LABEL_PREDICATES[pp[0]], two, pp[2]


def _get_names(graph: rdflib.Graph, uri_prefix: str) -> dict[str, str]:
    # Step 1, get the best possible label. Use a hierarchy of label types and languages
    names_dd: defaultdict[str, list[PP]] = defaultdict(list)
    for uri, predicate, name in graph.query(BEST_NAME_QUERY):
        if not uri.startswith(uri_prefix):
            continue
        names_dd[uri.removeprefix(uri_prefix)].append((predicate, name._language, name._label))

    names: dict[str, str] = {
        identifier: min(pps, key=_rank_pp)[2] for identifier, pps in names_dd.items()
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

    rv = []

    names = _get_names(graph, uri_prefix)

    for uri, name in graph.query(ALL_NAME_QUERY):
        if not uri.startswith(uri_prefix):
            continue
        identifier = uri.removeprefix(uri_prefix)
        rv.append(
            LiteralMapping(
                reference=NamableReference(
                    prefix=curie_prefix,
                    identifier=identifier,
                    name=names.get(identifier) or str(name),
                ),
                text=str(name),
                language=name._language,
                predicate=has_label,
            )
        )

    for uri, synonym in graph.query(SYNONYM_QUERY):
        if not uri.startswith(uri_prefix):
            continue
        identifier = uri.removeprefix(uri_prefix)
        rv.append(
            LiteralMapping(
                reference=NamableReference(
                    prefix=curie_prefix, identifier=identifier, name=names.get(identifier)
                ),
                text=str(synonym),
                language=synonym._language,
            )
        )

    return rv
