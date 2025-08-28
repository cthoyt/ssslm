"""Read literal mappings from RDF."""

import rdflib
from ssslm import LiteralMapping
from curies import NamableReference
from curies.vocabulary import has_label

__all__ = [
    "read_from_skos_graph",
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


def read_from_skos_graph(graph: rdflib.Graph, prefix: str, uri_prefix: str) -> list[LiteralMapping]:
    """Read literal mappings from a SKOS vocabulary."""
    rv = []

    # Step 1, get the best possible label. Use a hierarchy of label types and languages
    names = {
        uri.removeprefix(uri_prefix): str(name) for uri, name in graph.query(BEST_NAME_QUERY)
    }

    for uri, name in graph.query(ALL_NAME_QUERY):
        if not uri.startswith(uri_prefix):
            continue
        identifier = uri.removeprefix(uri_prefix)
        rv.append(
            LiteralMapping(
                reference=NamableReference(
                    prefix=prefix,
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
                    prefix=prefix, identifier=identifier, name=names.get(identifier)
                ),
                text=str(synonym),
                language=synonym._language,
            )
        )

    return rv
