"""NER utilities build on literal mappings."""

from __future__ import annotations

import enum
import importlib.util
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from functools import lru_cache, partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeGuard, Union

from curies import NamableReference, NamedReference
from pydantic import BaseModel
from typing_extensions import Self

from .model import (
    GildaErrorPolicy,
    LiteralMapping,
    literal_mappings_to_gilda,
    read_literal_mappings,
)

if TYPE_CHECKING:
    import gilda
    import pandas as pd

__all__ = [
    "Annotation",
    "Annotator",
    "GildaGrounder",
    "Grounder",
    "GrounderHint",
    "Match",
    "Matcher",
    "PandasTargetType",
    "make_grounder",
]

Implementation: TypeAlias = Literal["gilda"]

#: A type for an object can be coerced into a SSSLM-backed grounder via :func:`make_grounder`
GrounderHint: TypeAlias = Union[Iterable[LiteralMapping], str, Path, "gilda.Grounder", "Grounder"]


def make_grounder(
    grounder_hint: GrounderHint,
    *,
    implementation: Implementation | None = None,
    **kwargs: Any,
) -> Grounder:
    """Get a grounder from literal mappings.

    :param grounder_hint: An object that can be coerced into a SSSLM-backed grounder.
        Can be one of the following:

        1. A URL or file path
        2. An iterable of literal mappings
        3. A pre-instantiated grounder or gilda grounder
    :param implementation: If literal mappings are passed, what kind of grounder to use
    :param kwargs: If literal mappings are passed, keyword arguments passed to the
        construction of the grounder

    :returns: A SSSLM standard grounder

    A grounder can be constructed from a URL. In the following example, a pre-processed
    lexical index of anatomical terms from UBERON, BTO, MeSH, and other resources is
    loaded from the :mod:`biolexica` project.

    .. code-block:: python

        import ssslm

        url = f"https://github.com/biopragmatics/biolexica/raw/main/lexica/anatomy/anatomy.ssslm.tsv.gz"
        grounder = ssslm.make_grounder(url)

        match = grounder.get_best_match("purkinje cell")

    A grounder can be constructed from literal mappings that are already stored in a
    Python object. This example uses the same lexical index as above, first loading it
    by URL.

    .. code-block:: python

        import ssslm

        url = f"https://github.com/biopragmatics/biolexica/raw/main/lexica/anatomy/anatomy.ssslm.tsv.gz"
        literal_mappings = ssslm.read_literal_mappings(url)
        grounder = ssslm.make_grounder(literal_mappings)

        match = grounder.get_best_match("purkinje cell")

    A grounder can be constructed from a pre-existing :mod:`gilda.Grounder` object. As
    SSSLM is extended, this will incorporate other grounder interfaces.

    .. code-block:: python

        import ssslm
        from gilda.api import grounder as gilda_default_grounder

        grounder = ssslm.make_grounder(gilda_default_grounder)

        match = grounder.get_best_match("purkinje cell")
    """
    if isinstance(grounder_hint, Grounder):
        return grounder_hint
    if _is_gilda_grounder(grounder_hint):
        return GildaGrounder(grounder_hint)
    if isinstance(grounder_hint, str | Path):
        grounder_hint = read_literal_mappings(grounder_hint)

    if implementation is None or implementation == "gilda":
        return GildaGrounder.from_literal_mappings(grounder_hint, **kwargs)
    raise ValueError(f"Unsupported implementation: {implementation}")


def _is_gilda_grounder(obj: Any) -> TypeGuard[gilda.Grounder]:
    if not importlib.util.find_spec("gilda"):
        return False

    import gilda

    return isinstance(obj, gilda.Grounder)


class Match(BaseModel):
    """A match from NER."""

    reference: NamableReference
    score: float

    @property
    def prefix(self) -> str:
        """Get the scored match's term's prefix."""
        return self.reference.prefix

    @property
    def identifier(self) -> str:
        """Get the scored match's term's identifier."""
        return self.reference.identifier

    @property
    def curie(self) -> str:
        """Get the scored match's CURIE."""
        return self.reference.curie

    @property
    def name(self) -> str | None:
        """Get the scored match's term's name."""
        return self.reference.name


class Annotation(BaseModel):
    """Data about an annotation."""

    text: str
    start: int
    end: int
    match: Match

    @property
    def reference(self) -> NamableReference:
        """Get the scored match's reference."""
        return self.match.reference

    @property
    def prefix(self) -> str:
        """Get the scored match's term's prefix."""
        return self.reference.prefix

    @property
    def identifier(self) -> str:
        """Get the scored match's term's identifier."""
        return self.reference.identifier

    @property
    def curie(self) -> str:
        """Get the scored match's CURIE."""
        return self.reference.curie

    @property
    def name(self) -> str | None:
        """Get the scored match's term's name."""
        return self.reference.name

    @property
    def score(self) -> float:
        """Get the match's score."""
        return self.match.score

    @property
    def substr(self) -> str:
        """Get the substring that was matched."""
        return self.text[self.start : self.end]


class PandasTargetType(enum.Enum):
    """How should pandas columns be filled."""

    #: Fill columns with stringified CURIEs
    curie = enum.auto()
    #: Fill columns with :mod:`curies.NamableReference` objects
    reference = enum.auto()
    #: Fill columns with :mod:`ssslm.Match` objects
    match = enum.auto()


class Matcher(ABC):
    """An interface for a grounder."""

    @abstractmethod
    def get_matches(self, text: str, **kwargs: Any) -> list[Match]:
        """Get matches in the SSSLM format."""

    def get_best_match(self, text: str, **kwargs: Any) -> Match | None:
        """Get matches in the SSSLM format."""
        matches = self.get_matches(text, **kwargs)
        return matches[0] if matches else None

    def ground_df(
        self,
        df: pd.DataFrame,
        column: str | int,
        *,
        target_column: None | str | int = None,
        target_type: PandasTargetType | str = PandasTargetType.curie,
        **kwargs: Any,
    ) -> None:
        """Ground the elements of a column in a Pandas dataframe as CURIEs, in-place.

        :param df: A pandas dataframe
        :param column: The column to ground. This column contains text corresponding to
            named entities' labels or synonyms
        :param target_column: The column where to put the groundings (either a CURIE
            string, or None). It's possible to create a new column when passing a string
            for this argument. If not given, will create a new column name like
            ``<source column>_grounded``.
        :param target_type: The type to fill columns with
        :param kwargs: Keyword arguments passed to :meth:`Grounder.ground`, could
            include context, organisms, or namespaces.

        .. code-block:: python

            import pandas as pd
            import ssslm

            INDEX = "phenotype"
            mappings_url = f"https://github.com/biopragmatics/biolexica/raw/main/lexica/{INDEX}/{INDEX}.ssslm.tsv.gz"

            grounder = ssslm.make_grounder(mappings_url)

            data_url = "https://raw.githubusercontent.com/OBOAcademy/obook/master/docs/tutorial/linking_data/data.csv"
            df = pd.read_csv(data_url)

            grounder.ground_df(df, "disease", target_column="disease_curie")
        """
        if target_column is None:
            target_column = f"{column}_grounded"
        func = partial(_match_helper, matcher=self, target_type=target_type, **kwargs)
        df[target_column] = df[column].map(func)


def _match_helper(
    text: str, matcher: Matcher, target_type: PandasTargetType | str, **kwargs: Any
) -> str | None | Match | NamableReference:
    if not isinstance(text, str):  # this catches pd.nan's
        return None
    match = matcher.get_best_match(text, **kwargs)
    if not match:
        return None
    if isinstance(target_type, str):
        target_type = PandasTargetType[target_type]
    if target_type == PandasTargetType.curie:
        return match.curie
    elif target_type == PandasTargetType.match:
        return match
    elif target_type == PandasTargetType.reference:
        return match.reference
    raise TypeError


class Annotator(ABC):
    """An interface for something that can annotate."""

    @abstractmethod
    def annotate(self, text: str, **kwargs: Any) -> list[Annotation]:
        """Annotate the text."""


class Grounder(Matcher, Annotator, ABC):
    """A combine matcher and annotator."""


@lru_cache(1)
def _ensure_nltk() -> None:
    """Ensure NLTK data is downloaded properly."""
    import nltk.data
    import pystow

    directory = pystow.join("nltk")
    nltk.download("stopwords", download_dir=directory, quiet=True)
    nltk.data.path.append(directory)

    # this is cached so you don't have to keep checking
    # if the package was downloaded


class GildaGrounder(Grounder):
    """A grounder and annotator that uses gilda as a backend."""

    def __init__(self, grounder: gilda.Grounder) -> None:
        """Initialize a grounder wrapping a :class:`gilda.Grounder`."""
        _ensure_nltk()  # very important - do this before importing gilda.ner

        import gilda.ner

        self._grounder = grounder
        self._annotate = gilda.ner.annotate

    @classmethod
    def from_literal_mappings(
        cls,
        literal_mappings: Iterable[LiteralMapping],
        *,
        prefix_priority: list[str] | None = None,
        grounder_cls: type[gilda.Grounder] | None = None,
        filter_duplicates: bool = True,
        on_error: GildaErrorPolicy = "ignore",
    ) -> Self:
        """Initialize a grounder wrapping a :class:`gilda.Grounder`.

        :param literal_mappings: The literal mappings to populate the grounder
        :param prefix_priority: The priority list of prefixes to break ties. Maps to
            ``namespace_priority`` in :meth:`gilda.Grounder.__init__`
        :param grounder_cls: A custom subclass of :class:`gilda.Grounder`, if given.
        :param filter_duplicates: Should duplicates be filtered using
            :func:`gilda.term.filter_out_duplicates`? Defaults to true.
        :param on_error: The policy for what to do on error converting to Gilda
        """
        if grounder_cls is None:
            import gilda

            grounder_cls = gilda.Grounder

        terms = literal_mappings_to_gilda(literal_mappings, on_error=on_error)
        if filter_duplicates:
            from gilda.term import filter_out_duplicates

            # suppress logging counting of terms
            logging.getLogger("gilda.term").setLevel(logging.WARNING)
            terms = filter_out_duplicates(terms)
        grounder = grounder_cls(terms, namespace_priority=prefix_priority)
        return cls(grounder)

    @staticmethod
    def _convert_gilda_match(scored_match: gilda.ScoredMatch) -> Match:
        """Wrap a Gilda scored match."""
        return Match(
            reference=NamedReference(
                prefix=scored_match.term.db,
                identifier=scored_match.term.id,
                name=scored_match.term.entry_name,
            ),
            score=scored_match.score,
        )

    def get_matches(  # type:ignore[override]
        self,
        text: str,
        context: str | None = None,
        organisms: list[str] | None = None,
        namespaces: list[str] | None = None,
    ) -> list[Match]:
        """Get matches in the SSSLM format using :meth:`gilda.Grounder.ground`."""
        return [
            self._convert_gilda_match(scored_match)
            for scored_match in self._grounder.ground(
                text, context=context, organisms=organisms, namespaces=namespaces
            )
        ]

    def annotate(self, text: str, **kwargs: Any) -> list[Annotation]:
        """Annotate the text."""
        return [
            Annotation(
                text=text,
                match=self._convert_gilda_match(match),
                start=annotation.start,
                end=annotation.end,
            )
            for annotation in self._annotate(text, grounder=self._grounder, **kwargs)
            for match in annotation.matches
        ]
