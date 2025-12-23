"""Parse BioC."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import bioc.pubtator
import pandas as pd
import pystow
from bioc.pubtator import PubTator
from curies import NamableReference, NamedReference
from curies.vocabulary import abstract_section, title_section
from pydantic import BaseModel
from tqdm import tqdm

from ssslm.ner import Annotation, Match

if TYPE_CHECKING:
    from ssslm import Grounder

__all__ = [
    "Document",
]

MODULE = pystow.module("bioc")


class Document(BaseModel):
    """Represent a document from the BioC format."""

    reference: NamableReference
    text: str
    document_part: NamableReference
    annotations: list[Annotation]


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
        if prefix is not None:
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


def evaluate_path(
    path: str | Path,
    *,
    prefix: str | None = None,
    grounder: Grounder | None = None,
    confidence: float | None = None,
) -> None:
    import bioc.pubtator

    with Path(path).expanduser().open() as file:
        evaluate(
            bioc.pubtator.iterparse(file),
            grounder=grounder,
            prefix=prefix,
            confidence=confidence,
        )


def evaluate(
    pubtators: Iterable[PubTator],
    *,
    grounder: Grounder | None = None,
    confidence: float | None = None,
    prefix: str | None = None,
) -> None:
    """Evaluate a BioC file against a grounder."""
    import seaborn as sns

    if grounder is None:
        import pyobo

        grounder = pyobo.get_grounder("mesh")

    precisions = []
    for pubtator in tqdm(pubtators, unit_scale=True):
        for document in _pubtator_to_documents(pubtator, prefix=prefix, confidence=confidence):
            result = _compare(
                document.annotations,
                grounder.annotate(document.text),
            )
            if result is not None:
                precisions.append(result)
            else:
                tqdm.write(f"{document.reference.curie}: NaN (no ground truth)")

    df = pd.DataFrame(precisions)
    g = sns.displot(
        data=df.melt(var_name="variable", value_name="value"),
        x="value",
        col="variable",
        bins=30,
        height=4,
        aspect=1.7,
    )
    for ax in g.axes.flatten():
        ax.set_yscale("log")
    g.figure.savefig("/Users/cthoyt/Desktop/results.png", dpi=400)


class Evaluation(TypedDict):
    """A collection of metrics."""

    offsets_recall: float | None
    entities_recall: float | None


def _compare(expected: list[Annotation], actual: list[Annotation]) -> Evaluation | None:
    expected_offsets = {(a.start, a.end) for a in expected}
    actual_offsets = {(a.start, a.end) for a in actual}
    offsets_intersection = actual_offsets.intersection(expected_offsets)

    expected_entities = {a.reference.curie for a in expected}
    actual_entities = {a.reference.curie for a in actual}
    entities_intersection = actual_entities.intersection(expected_entities)

    if not expected_offsets:
        offsets_recall = None
    else:
        offsets_recall = len(offsets_intersection) / len(expected_offsets)

    if not expected_entities:
        entities_recall = None
    else:
        entities_recall = len(entities_intersection) / len(expected_entities)

    rv = Evaluation(offsets_recall=offsets_recall, entities_recall=entities_recall)
    if all(v is None for v in rv.values()):
        return None
    return rv


BC5_CDR_URL = "https://github.com/JHnlp/BioCreative-V-CDR-Corpus/raw/refs/heads/master/CDR_Data.zip"
BC5_CDR_EVALUATION_URL = "https://github.com/JHnlp/BioCreative-V-CDR-Corpus/raw/refs/heads/master/BC5CDR_Evaluation-0.0.3.zip"


def load_bc5_cdr_development() -> list[PubTator]:
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CDR_DevelopmentSet.PubTator.txt")


def load_bc5_cdr_test() -> list[PubTator]:
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CCDR_TestSet.PubTator.txt")


def load_bc5_cdr_training() -> list[PubTator]:
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CDR_TrainingSet.PubTator.txt")


def load_bc5_dorm_test() -> list[PubTator]:
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5("DNorm.TestSet/TestSet.DNorm.PubTator.txt")


def load_bc5_tmchem_test() -> list[PubTator]:
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5("tmChem.TestSet/TestSet.tmChem.PubTator.txt")


def _load_bc5(inner_path: str) -> list[PubTator]:
    with MODULE.ensure_open_zip(
        url=BC5_CDR_URL, inner_path="CDR_Data/" + inner_path, mode="rt"
    ) as zf:
        return bioc.pubtator.load(zf)


def load_bc5_evaluation_sample() -> list[PubTator]:
    # annotated with MeSH LUIDs
    return _load_bc5_evaluation("data/gold/CDR_sample.gold.PubTator")


def load_bc5_evaluation_cid() -> list[PubTator]:
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5_evaluation("data/test/CDR_sample.test.CID.PubTator")


def load_bc5_evaluation_dner() -> list[PubTator]:
    # this one is annotated with CURIEs from MESH
    return _load_bc5_evaluation("data/test/CDR_sample.test.DNER.PubTator")


def _load_bc5_evaluation(inner_path: str) -> list[PubTator]:
    with MODULE.ensure_open_zip(url=BC5_CDR_EVALUATION_URL, inner_path=inner_path, mode="rt") as zf:
        return bioc.pubtator.load(zf)


if __name__ == "__main__":
    evaluate(load_bc5_dorm_test())
