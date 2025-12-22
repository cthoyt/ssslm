"""Parse BioC."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from curies import NamableReference, NamedReference
from curies.vocabulary import abstract_section, title_section
from pydantic import BaseModel

from ssslm.ner import Annotation, Match

if TYPE_CHECKING:
    from bioc.pubtator import PubTator

    from ssslm import Grounder

__all__ = [
    "Document",
    "parse_pubtator",
]


class Document(BaseModel):
    """Represent a document from the BioC format."""

    reference: NamableReference
    text: str
    document_part: NamableReference
    annotations: list[Annotation]


def parse_pubtator(
    path: str | Path, *, prefix: str | None = None, confidence: float | None = None
) -> Iterable[Document]:
    """Parse a BioC PubTator file."""
    import bioc.pubtator

    if confidence is None:
        confidence = 1.0
    if prefix is None:
        prefix = "mesh"

    with Path(path).expanduser().open() as file:
        for pubtator in bioc.pubtator.iterparse(file):
            yield from _pubtator_to_documents(pubtator, confidence=confidence, prefix=prefix)


def _pubtator_to_documents(
    pubtator: PubTator, *, prefix: str | None, confidence: float
) -> list[Document]:
    """Consume a PubTator object."""
    document_reference = NamedReference(
        prefix="pubmed", identifier=pubtator.pmid, name=pubtator.title
    )

    title_annotations = []
    abstract_annotations = []

    title_len = len(pubtator.title)
    for annotation in pubtator.annotations:
        if prefix:
            annotation_reference = NamableReference(prefix=prefix, identifier=annotation.id)
        else:
            annotation_reference = NamableReference.from_curie(annotation.id)
        match = Match(reference=annotation_reference, score=confidence)

        if annotation.end <= title_len:
            annotation = Annotation(
                start=annotation.start,
                end=annotation.end,
                text=pubtator.title,
                match=match,
            )
            title_annotations.append(annotation)

        else:
            annotation = Annotation(
                start=annotation.start - title_len - 1,
                end=annotation.end - title_len,
                text=pubtator.abstract,
                match=match,
            )
            abstract_annotations.append(annotation)

    d1 = Document(
        reference=document_reference,
        text=pubtator.text,
        document_part=title_section,
        annotations=title_annotations,
    )
    d2 = Document(
        reference=document_reference,
        text=pubtator.abstract,
        document_part=abstract_section,
        annotations=abstract_annotations,
    )

    return [d1, d2]


def evaluate_recall(
    *, grounder: Grounder | None = None, path: str | Path, prefix: str | None = None
) -> None:
    """Evaluate a BioC file against a grounder."""
    import click

    if grounder is None:
        import pyobo

        grounder = pyobo.get_grounder("mesh")

    for document in parse_pubtator(path, prefix=prefix):
        result = _compare(
            document.annotations,
            grounder.annotate(document.text),
        )
        click.echo(f"{document.reference.curie}: {result:.2f}")


def _compare(expected: list[Annotation], actual: list[Annotation]) -> float:
    expected_offsets = {(a.start, a.end) for a in expected}
    actual_offsets = {(a.start, a.end) for a in actual}
    intersection = actual_offsets.intersection(expected_offsets)
    recall = len(intersection) / len(expected_offsets)
    return recall


if __name__ == "__main__":
    evaluate_recall(path="/Users/cthoyt/dev/BioCreative-V-CDR-Corpus/CDR_sample.txt")
