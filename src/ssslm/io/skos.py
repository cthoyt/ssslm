"""Read literal mappings from RDF."""

import rdflib
from curies import NamableReference
from curies.vocabulary import has_label

from ssslm import LiteralMapping

__all__ = [
    "read_from_skos",
]

BEST_NAME_QUERY = """\
    SELECT ?uri ?name
    WHERE {
        ?uri skos:prefLabel|rdfs:label ?name .
        FILTER(LANG(?name) = 'en')
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


def read_from_skos(
    graph: str | rdflib.Graph, curie_prefix: str | None = None, uri_prefix: str | None = None
) -> list[LiteralMapping]:
    """Read literal mappings from a SKOS vocabulary."""
    graph = _ensure_graph(graph)
    curie_prefix, uri_prefix = _ensure_prefixes(
        graph, curie_prefix=curie_prefix, uri_prefix=uri_prefix
    )

    rv = []

    # Step 1, get the best possible label. Use a hierarchy of label types and languages
    names = {uri.removeprefix(uri_prefix): str(name) for uri, name in graph.query(BEST_NAME_QUERY)}

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
