"""Evaluate the BioCreative V - Chemical Drug Relation (CDR) task."""

from __future__ import annotations

import itertools as itt

import bioc.pubtator
import pystow
from bioc.pubtator import PubTator
import click
from more_click import verbose_option
from ssslm.io.bioc_w import evaluate_pubtators

BC5_CDR_URL = "https://github.com/JHnlp/BioCreative-V-CDR-Corpus/raw/refs/heads/master/CDR_Data.zip"
BC5_CDR_EVALUATION_URL = "https://github.com/JHnlp/BioCreative-V-CDR-Corpus/raw/refs/heads/master/BC5CDR_Evaluation-0.0.3.zip"

MODULE = pystow.module("bioc")


def load_bc5_cdr_development() -> list[PubTator]:  # noqa:D103
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CDR_DevelopmentSet.PubTator.txt")


def load_bc5_cdr_test() -> list[PubTator]:  # noqa:D103
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CDR_TestSet.PubTator.txt")


def load_bc5_cdr_training() -> list[PubTator]:  # noqa:D103
    # annotated with MeSH LUIDs
    return _load_bc5("CDR.Corpus.v010516/CDR_TrainingSet.PubTator.txt")


def load_bc5_dorm_test() -> list[PubTator]:  # noqa:D103
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5("DNorm.TestSet/TestSet.DNorm.PubTator.txt")


def load_bc5_tmchem_test() -> list[PubTator]:  # noqa:D103
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5("tmChem.TestSet/TestSet.tmChem.PubTator.txt")


def _load_bc5(inner_path: str) -> list[PubTator]:
    with MODULE.ensure_open_zip(
        "input", url=BC5_CDR_URL, inner_path="CDR_Data/" + inner_path, mode="rt"
    ) as zf:
        return bioc.pubtator.load(zf)  # type:ignore


def load_bc5_evaluation_sample() -> list[PubTator]:  # noqa:D103
    # annotated with MeSH LUIDs
    return _load_bc5_evaluation("data/gold/CDR_sample.gold.PubTator")


def load_bc5_evaluation_cid() -> list[PubTator]:  # noqa:D103
    # this one is annotated with CURIEs from MESH and CHEBI
    return _load_bc5_evaluation("data/test/CDR_sample.test.CID.PubTator")


def load_bc5_evaluation_dner() -> list[PubTator]:  # noqa:D103
    # this one is annotated with CURIEs from MESH
    return _load_bc5_evaluation("data/test/CDR_sample.test.DNER.PubTator")


def _load_bc5_evaluation(inner_path: str) -> list[PubTator]:
    with MODULE.ensure_open_zip(
        "input",
        url=BC5_CDR_EVALUATION_URL,
        inner_path="BC5CDR_Evaluation-0.0.3/" + inner_path,
        mode="rt",
    ) as zf:
        return bioc.pubtator.load(zf)  # type:ignore


LUIDS = {
    load_bc5_cdr_development,
    load_bc5_cdr_test,
    load_bc5_cdr_training,
    load_bc5_evaluation_sample,
}
CURIES = {
    load_bc5_dorm_test,
    load_bc5_tmchem_test,
    load_bc5_evaluation_cid,
    load_bc5_evaluation_dner,
}


@click.command()
@verbose_option
def main() -> None:
    """Run the benchmark."""
    xx = {
        func.__name__.removeprefix("load_"): func()
        for func in LUIDS
    }
    yy = {
        func.__name__.removeprefix("load_"): func()
        for func in CURIES
    }

    import pandas as pd
    import pyobo

    dfs = []
    for year in ["2018", "2023", "2025"]:
        grounder = pyobo.get_grounder(["mesh", "chebi"], versions=[year, None])

        tt = itt.chain(
            zip(xx.items(), itt.repeat("mesh")),
            zip(yy.items(), itt.repeat(None)),
        )
        for (dataset, pubtators), prefix in tt:
            df = evaluate_pubtators(
                pubtators,
                grounder=grounder,
                directory=MODULE.join(year, dataset),
                prefix=prefix,
                year=year,
                dataset=dataset,
            )
            dfs.append(df)

    mega_df = pd.concat(dfs)
    path = MODULE.join(name="full.tsv")
    mega_df.to_csv(path, sep="\t", index=False)


if __name__ == "__main__":
    main()
