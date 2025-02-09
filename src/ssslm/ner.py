"""NER utilities build on literal mappings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Literal, Self, TypeAlias

from curies import NamableReference, NamedReference
from pydantic import BaseModel

from .model import LiteralMapping

if TYPE_CHECKING:
    import gilda

__all__ = [
    "Annotation",
    "Annotator",
    "GildaGrounder",
    "Grounder",
    "Match",
    "Matcher",
    "make_grounder",
]

Implementation: TypeAlias = Literal["gilda"]


def make_grounder(
    literal_mappings: Iterable[LiteralMapping],
    *,
    implementation: Implementation | None = None,
    **kwargs: Any,
) -> Grounder:
    """Get a grounder from literal mappings."""
    if implementation is None or implementation == "gilda":
        return GildaGrounder.from_literal_mappings(literal_mappings, **kwargs)
    raise ValueError(f"Unsupported implementation: {implementation}")


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


class Matcher(ABC):
    """An interface for a grounder."""

    @abstractmethod
    def get_matches(self, text: str, **kwargs: Any) -> list[Match]:
        """Get matches in the SSSLM format."""

    def get_best_match(self, text: str, **kwargs: Any) -> Match | None:
        """Get matches in the SSSLM format."""
        matches = self.get_matches(text, **kwargs)
        return matches[0] if matches else None


class Annotator(ABC):
    """An interface for something that can annotate."""

    @abstractmethod
    def annotate(self, text: str, **kwargs: Any) -> list[Annotation]:
        """Annotate the text."""


class Grounder(Matcher, Annotator, ABC):
    """A combine matcher and annotator."""


def _ensure_nltk() -> None:
    """Ensure NLTK data is downloaded properly."""
    import nltk.data
    import pystow

    directory = pystow.join("nltk")
    nltk.download("stopwords", download_dir=directory)
    nltk.data.path.append(directory)


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
    ) -> Self:
        """Initialize a grounder wrapping a :class:`gilda.Grounder`.

        :param literal_mappings: The literal mappings to populate the grounder
        :param prefix_priority: The priority list of prefixes to break ties. Maps to
            ``namespace_priority`` in :meth:`gilda.Grounder.__init__`
        :param grounder_cls: A custom subclass of :class:`gilda.Grounder`, if given.
        :param filter_duplicates: Should duplicates be filtered using
            :func:`gilda.term.filter_out_duplicates`? Defaults to true.

        """
        from gilda.term import filter_out_duplicates

        if grounder_cls is None:
            import gilda

            grounder_cls = gilda.Grounder

        terms = [m.to_gilda() for m in literal_mappings]
        if filter_duplicates:
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
