"""Parse BioC."""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import bioc.pubtator
import pandas as pd
from bioc.pubtator import PubTator
from curies import NamableReference, NamedReference
from curies.vocabulary import abstract_section, title_section
from tqdm import tqdm

from ssslm.benchmarking.utils import Document, evaluate
from ssslm.ner import Annotation, Match

if TYPE_CHECKING:
    from ssslm import Grounder


def read_documents(
    path: str | Path,
    prefix: str | None = None,
    confidence: float | None = None,
) -> Iterable[Document]:
    """Read documents."""
    for pubtator in tqdm(read_pubtators(path), unit_scale=True):
        yield from pubtator_to_documents(pubtator, prefix=prefix, confidence=confidence)


def pubtator_to_documents(
    pubtator: PubTator, *, prefix: str | None = None, confidence: float
) -> list[Document]:
    """Extract two documents from a PubTator object."""
    document_reference = NamedReference(
        prefix="pubmed", identifier=pubtator.pmid, name=pubtator.title
    )

    title_annotations = []
    abstract_annotations = []

    title_len = len(pubtator.title)
    for annotation in pubtator.annotations:
        if ":" in annotation.id:
            annotation_reference = NamableReference.from_curie(annotation.id)
        elif annotation.id.startswith("D") or annotation.id.startswith("C"):
            # assume MeSH
            annotation_reference = NamableReference(prefix="mesh", identifier=annotation.id)
        elif prefix is not None:
            annotation_reference = NamableReference(prefix=prefix, identifier=annotation.id)
        else:
            tqdm.write(f"could not parse ID: {annotation.id}")
            continue

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


def read_pubtators(path: str | Path) -> Iterable[bioc.pubtator.PubTator]:
    """Evaluate a BioC file against a grounder."""
    import bioc.pubtator

    with Path(path).expanduser().open() as file:
        yield from bioc.pubtator.iterparse(file)


def evaluate_path(
    path: str | Path,
    *,
    prefix: str | None = None,
    grounder: Grounder | None = None,
    confidence: float | None = None,
    directory: str | Path,
) -> pd.DataFrame:
    """Evaluate a BioC file against a grounder."""
    return evaluate_pubtators(
        read_pubtators(path),
        grounder=grounder,
        prefix=prefix,
        confidence=confidence,
        directory=directory,
    )


def evaluate_pubtators(
    pubtators: Iterable[PubTator],
    *,
    grounder: Grounder | None = None,
    confidence: float | None = None,
    prefix: str | None = None,
    directory: str | Path,
    **kwargs: Any,
) -> pd.DataFrame:
    """Evaluate BioC PubTator annotations against a grounder."""
    if grounder is None:
        import humanize
        import pyobo

        tqdm.write("getting mesh grounder")
        start = time.time()
        grounder = pyobo.get_grounder("mesh", versions="2025", use_tqdm=True)
        tqdm.write(f"got mesh grounder in {humanize.naturaltime(time.time() - start)}")

    if confidence is None:
        confidence = 1.0

    documents = (
        document
        for pubtator in tqdm(pubtators, unit_scale=True)
        for document in pubtator_to_documents(pubtator, prefix=prefix, confidence=confidence)
    )
    return evaluate(documents=documents, grounder=grounder, directory=directory, **kwargs)
