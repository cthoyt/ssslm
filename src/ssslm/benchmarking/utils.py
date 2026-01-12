"""Benchmarking utilities."""

from __future__ import annotations

import itertools as itt
from collections import Counter
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypedDict, TypeVar

import pandas as pd
import seaborn as sns
from curies import NamableReference
from pydantic import BaseModel

if TYPE_CHECKING:
    from ssslm import Annotation, Grounder

__all__ = [
    "Document",
    "Evaluation",
    "compare_annotations",
    "evaluate",
]

X = TypeVar("X")


class Document(BaseModel):
    """Represent a document from the BioC format."""

    reference: NamableReference
    text: str
    document_part: NamableReference
    annotations: list[Annotation]


def evaluate(
    documents: Iterable[Document],
    *,
    grounder: Grounder,
    directory: str | Path,
    output_figures: bool = False,
    **kwargs: Any,
) -> pd.DataFrame:
    """Evaluate a set of documents."""
    directory = Path(directory).expanduser().resolve()
    results = []
    for document in documents:
        result = compare_annotations(
            document.annotations,
            grounder.annotate(document.text),
        )
        results.append({**result, **kwargs})

    df = pd.DataFrame(results)
    df.to_csv(directory.joinpath("results.tsv"), index=False, sep="\t")

    if output_figures:
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
        g.figure.savefig(directory.joinpath("results.svg"))
        g.figure.savefig(directory.joinpath("results.png"), dpi=400)

    return df


class Evaluation(TypedDict):
    """A collection of metrics."""

    offsets_recall: float
    offsets_precision: float
    offsets_f1: float

    # entities is an easier problem since it only checks if
    # the right thing was detected, and not where
    entities_recall: float
    entities_precision: float
    entities_f1: float


def _prepare_grouped_comparison(
    reference_annotations: dict[X, list[Annotation]], grounder: Grounder
) -> dict[X, list[Annotation]]:
    """Evaluate a set of documents."""
    return {
        key: _prepare_comparison(annotations_, grounder)
        for key, annotations_ in reference_annotations.items()
    }


def _prepare_comparison(
    reference_annotations: list[Annotation], grounder: Grounder
) -> list[Annotation]:
    """Evaluate a set of documents."""
    unique_texts = {annotation.text for annotation in reference_annotations}
    return _chain_from_iterable(grounder.annotate(text) for text in unique_texts)


def _chain_from_iterable(x: Iterable[Iterable[X]]) -> list[X]:
    return list(itt.chain.from_iterable(x))


def evaluate_grouped(
    left: dict[X, list[Annotation]],
    right: dict[X, list[Annotation]],
    strategy: Literal["ungroup", "group"] = "group",
) -> Evaluation:
    """Evaluate grouped annotations."""
    if strategy == "ungroup":
        return compare_annotations(
            _chain_from_iterable(left.values()),
            _chain_from_iterable(left.values()),
        )
    elif strategy == "group":
        return aggregate_evaluations(_evaluate_grouped(left, right).values())
    else:
        raise ValueError(f"unknown strategy: {strategy}")


def _evaluate_grouped(
    left: dict[X, list[Annotation]], right: dict[X, list[Annotation]]
) -> dict[X, Evaluation]:
    if set(left) != set(right):
        raise ValueError("keys are not the same")
    rr = {}
    for key, left_annotations in left.items():
        right_annotations = right[key]
        rr[key] = compare_annotations(left_annotations, right_annotations)
    return rr


def aggregate_evaluations(evaluations: Collection[Evaluation]) -> Evaluation:
    """Aggregate multiple evaluations."""
    if not evaluations:
        raise ValueError
    n = len(evaluations)
    totals: Counter[str] = Counter()
    for evaluation in evaluations:
        for key, value in evaluation.items():
            totals[key] += value
    return Evaluation(**{key: value / n for key, value in totals.items()})


def compare_annotations(expected: list[Annotation], actual: list[Annotation]) -> Evaluation:
    """Compare two sets of annotations."""
    expected_offsets = {(a.start, a.end, a.reference.curie) for a in expected}
    actual_offsets = {(a.start, a.end, a.reference.curie) for a in actual}
    offsets_precision, offsets_recall, offsets_f1 = _get_metrics(expected_offsets, actual_offsets)

    expected_entities = {a.reference.curie for a in expected}
    actual_entities = {a.reference.curie for a in actual}
    entities_precision, entities_recall, entities_f1 = _get_metrics(
        expected_entities, actual_entities
    )
    return Evaluation(
        offsets_precision=offsets_precision,
        offsets_recall=offsets_recall,
        offsets_f1=offsets_f1,
        entities_precision=entities_precision,
        entities_recall=entities_recall,
        entities_f1=entities_f1,
    )


#: A small number to avoid division by zero issues
EPSILON = 1e-9


def _get_metrics(expected_offsets: set[X], actual_offsets: set[X]) -> tuple[float, ...]:
    tp = len(expected_offsets & actual_offsets)
    fp = len(expected_offsets - actual_offsets)
    fn = len(actual_offsets - expected_offsets)
    recall = tp / max(tp + fn, EPSILON)
    precision = tp / max(tp + fp, EPSILON)
    f1 = 2 * tp / max(2 * tp + fp + fn, EPSILON)
    return precision, recall, f1
