"""Read literal mappings from RDF."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache
from typing import TYPE_CHECKING, NamedTuple, cast, overload

import curies
from curies import NamableReference, NamedReference, Reference, ReferenceTuple
from curies.vocabulary import (
    has_label,
    has_title,
    skos_alt_label,
    skos_hidden_label,
    skos_pref_label,
)

from ..model import LiteralMapping, R

if TYPE_CHECKING:
    import rdflib

__all__ = [
    "read_skos",
]


@lru_cache(1)
def _get_label_predicates() -> dict[rdflib.URIRef, int]:
    from rdflib import RDFS, SKOS

    return {
        RDFS.label: 0,
        SKOS.prefLabel: 1,
    }


@lru_cache(1)
def _get_predicate_to_ref(*, include_extras: bool = False) -> dict[rdflib.URIRef, Reference]:
    from rdflib import DC, DCTERMS, FOAF, RDFS, SDO, SKOS

    rv = {
        RDFS.label: has_label,
        SKOS.prefLabel: skos_pref_label,
        SKOS.altLabel: skos_alt_label,
        SKOS.hiddenLabel: skos_hidden_label,
    }
    if include_extras:
        rv.update(
            {
                DCTERMS.title: has_title,
                DC.title: has_title,
                SDO.name: NamedReference.from_curie("sdo:name", name="name"),
                FOAF.name: NamedReference.from_curie("foaf:name", name="name"),
            }
        )
    return rv


BEST_NAME_QUERY = """\
    SELECT ?uri ?predicate ?name
    WHERE {
        VALUES ?predicate { skos:prefLabel rdfs:label }
        ?uri ?predicate ?name .
    }
"""


@lru_cache(1)
def _get_literal_mapping_query() -> str:
    predicate_list = " ".join(predicate.curie for predicate in _get_predicate_to_ref().values())
    rv = f"""\
        SELECT ?uri ?predicate ?name
        WHERE {{
            VALUES ?predicate {{ {predicate_list} }}
            ?uri ?predicate ?name .
        }}
    """
    return rv


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
    import rdflib

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
        curie_prefix = str(curie_prefix_res[0][0])  # type:ignore[index]

    if not uri_prefix:
        uri_prefix_res = list(graph.query(GET_URI_PREFIX))
        if not uri_prefix_res:
            raise ValueError(
                "no URI prefix given and none could be looked up using vann:preferredNamespaceUri"
            )
        uri_prefix = str(uri_prefix_res[0][0])  # type:ignore[index]
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
        _get_label_predicates()[label_tuple.predicate],
        language_priority,
        label_tuple.language,
        label_tuple.value,
    )


def _get_names(graph: rdflib.Graph, converter: curies.Converter) -> dict[ReferenceTuple, str]:
    # Step 1, get the best possible label. Use a hierarchy of label types and languages
    names_dd: defaultdict[str, list[_LabelTuple]] = defaultdict(list)
    results = cast(
        Iterable["tuple[rdflib.URIRef, rdflib.URIRef, rdflib.Literal]"],
        graph.query(BEST_NAME_QUERY),
    )
    for uri, predicate, name in results:
        reference_tuple = converter.parse_uri(uri)
        if reference_tuple is None or not name._language:
            continue
        names_dd[reference_tuple].append(_LabelTuple(predicate, name._language, name._value))

    names: dict[str, str] = {
        reference_tuple: min(label_tuples, key=_rank_label_tuple).value
        for reference_tuple, label_tuples in names_dd.items()
    }
    return names


# docstr-coverage:excused `overload`
@overload
def read_skos(
    graph: str | rdflib.Graph,
    curie_prefix: str | None = ...,
    uri_prefix: str | None = ...,
    reference_cls: type[R] = ...,
) -> list[LiteralMapping[R]]: ...


# docstr-coverage:excused `overload`
@overload
def read_skos(
    graph: str | rdflib.Graph,
    curie_prefix: str | None = ...,
    uri_prefix: str | None = ...,
    reference_cls: None = ...,
) -> list[LiteralMapping[NamedReference]]: ...


def read_skos(
    graph: str | rdflib.Graph,
    curie_prefix: str | None = None,
    uri_prefix: str | None = None,
    reference_cls: type[R] | None = None,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamedReference]]:
    """Read literal mappings from a SKOS.

    :param graph: Either a URL to a SKOS concept scheme or a pre-parsed SKOS concept
        scheme in a :class:`rdflib.Graph`.
    :param curie_prefix: The CURIE prefix used to parse the SKOS graph. If not given,
        will try to infer by querying the vocabulary for a
        ``vann:preferredNamespacePrefix`` annotation on the SKOS concept scheme
    :param uri_prefix: The URI prefix used to identify terms from the SKOS vocabulary.
        If not given, will try to infer by querying the vocabulary for a
        ``vann:preferredNamespaceUri`` annotation on the SKOS concept scheme
    :param reference_cls: The reference type to use

    :returns: A list of literal mappings

    This function will look for ``rdfs:label``, ``skos:prefLabel``, and
    ``skos:altLabel``. It will automatically assign a canonical label prioritizing
    ``rdfs:label`` over ``skos:prefLabel`` and English over other languages. It
    maintains the predicates in the literal mappings and does not attempt to map to OBO
    in OWL predicates.

    .. warning::

        This function assumes there is only one ``skos:ConceptScheme`` in the graph

    Example usage:

    .. code-block:: python

        import ssslm

        url = "https://raw.githubusercontent.com/dini-ag-kim/schulfaecher/refs/heads/main/schulfaecher.ttl"
        literal_mappings = ssslm.read_skos(url)

    """
    graph = _ensure_graph(graph)
    curie_prefix, uri_prefix = _ensure_prefixes(
        graph, curie_prefix=curie_prefix, uri_prefix=uri_prefix
    )
    converter = curies.Converter.from_prefix_map({curie_prefix: uri_prefix})
    names = _get_names(graph, converter)
    return _read_rdf(graph=graph, converter=converter, reference_cls=reference_cls, names=names)


def _read_rdf(
    graph: str | rdflib.Graph,
    converter: curies.Converter,
    reference_cls: type[R] | None = None,
    names: dict[ReferenceTuple, str] | None = None,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamedReference]]:
    """Read literal mappings from a SKOS.

    :param graph: Either a URL to a SKOS concept scheme or a pre-parsed SKOS concept
        scheme in a :class:`rdflib.Graph`.
    :param converter: An instance of :class:`curies.Converter`.
    :param reference_cls: The reference type to use

    :returns: A list of literal mappings

    This function will look for ``rdfs:label``, ``skos:prefLabel``, and
    ``skos:altLabel``. It will automatically assign a canonical label prioritizing
    ``rdfs:label`` over ``skos:prefLabel`` and English over other languages. It
    maintains the predicates in the literal mappings and does not attempt to map to OBO
    in OWL predicates.

    .. warning::

        This function assumes there is only one ``skos:ConceptScheme`` in the graph

    Example usage:

    .. code-block:: python

        import ssslm

        url = "https://raw.githubusercontent.com/dini-ag-kim/schulfaecher/refs/heads/main/schulfaecher.ttl"
        literal_mappings = ssslm.read_skos(url)

    """
    graph = _ensure_graph(graph)

    if names is None:
        names = {}
    if reference_cls is None:
        reference_cls = NamedReference  # type:ignore
    assert reference_cls is not None  # noqa:S101

    predicate_uri_to_reference = _get_predicate_to_ref()

    results = cast(
        Iterable["tuple[rdflib.URIRef, rdflib.URIRef, rdflib.Literal]"],
        graph.query(_get_literal_mapping_query()),
    )
    # we're ignoring because we know the results will be homogenous
    rv: list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]] = [
        LiteralMapping(
            reference=reference_cls(
                prefix=reference_tuple.prefix,
                identifier=reference_tuple.identifier,
                name=names.get(reference_tuple),
            ),
            text=str(value),
            language=value._language,
            predicate=predicate_uri_to_reference[predicate_uri],
        )
        for uri, predicate_uri, value in results
        if (reference_tuple := converter.parse_uri(uri))
    ]
    return rv  # type:ignore[return-value]
