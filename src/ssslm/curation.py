"""SSSLM-based synonym curation harness.."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast

import click
from curies import Reference
from pydantic import BaseModel, Field

from .model import LiteralMapping, lint_literal_mappings, read_literal_mappings
from .ner import Grounder, make_grounder
from .ontology import write_owl_ttl

__all__ = [
    "Metadata",
    "Repository",
]

logger = logging.getLogger(__name__)


class Metadata(BaseModel):
    """Metadata for a curation program."""

    uri: str
    title: str | None = None
    description: str | None = None
    license: Reference | str | None = None
    comments: list[str] = Field(default_factory=list)


class Repository:
    """A configuration for a synonym curation repository."""

    def __init__(
        self,
        positives_path: str | Path,
        negatives_path: str | Path,
        stop_words_path: str | Path,
        *,
        metadata: Metadata | None = None,
        owl_ttl_path: str | Path | None = None,
    ) -> None:
        """Initialize the synonym curation configuration."""
        self.positives_path = positives_path
        self.negatives_path = negatives_path
        self.stop_words_path = stop_words_path
        self.metadata = metadata
        self.owl_path = owl_ttl_path

    def cli(self, *args: Any, **kwargs: Any) -> None:
        """Run the CLI."""
        return self.get_cli()(*args, **kwargs)

    def get_cli(self) -> click.Group:
        """Get a CLI."""

        @click.group()
        def main() -> None:
            """Run the CLI."""

        @main.command()
        def lint() -> None:
            """Lint the SSSLM files."""
            self.lint()

        @main.command()
        @click.option("--path", type=Path)
        def export(path: Path | None) -> None:
            """Export OWL."""
            self.write_owl_rdf(path=path)

        return main

    def get_positive_synonyms(self) -> list[LiteralMapping]:
        """Get positive synonyms curated in Biosynonyms."""
        return read_literal_mappings(self.positives_path)

    def get_negative_synonyms(self) -> list[LiteralMapping]:
        """Get negative synonyms curated in Biosynonyms."""
        return read_literal_mappings(self.negatives_path)

    def lint(self) -> None:
        """Lint the positive/negative mappings and stop words file."""
        lint_literal_mappings(self.positives_path)
        lint_literal_mappings(self.negatives_path)
        self.lint_stop_words()

    @staticmethod
    def _stop_words_key(row: Sequence[str]) -> str:
        return row[0].casefold()

    def write_stop_words(self, rows: Iterable[tuple[str, str]]) -> None:
        """Write all strings that are known not to be named entities."""
        with self.stop_words_path.open("w") as file:
            print("text", "curator_orcid", sep="\t", file=file)
            for row in sorted(rows, key=self._stop_words_key):
                print(*row, sep="\t", file=file)

    def lint_stop_words(self) -> None:
        """Lint the stop words file."""
        self.write_stop_words(sorted(self._load_stop_words_helper()))

    def load_stop_words(self) -> set[str]:
        """Load the stop words from the file as a set."""
        return {line[0] for line in self._load_stop_words_helper()}

    def _load_stop_words_helper(self) -> Iterable[tuple[str, str]]:
        with self.stop_words_path.open() as file:
            next(file)  # throw away header
            for line in file:
                yield cast(tuple[str, str], tuple(line.strip().split("\t")))

    def write_owl_rdf(self, path: str | Path | None = None, **kwargs: Any) -> None:
        """Write OWL RDF in a Turtle file."""
        if path is None and self.owl_path is None:
            raise ValueError
        elif path and self.owl_path is None:
            pass
        elif path is None and self.owl_path is not None:
            path = self.owl_path
        else:
            logger.warning("internal path and explicit path give, using explicit path")

        write_owl_ttl(self.get_positive_synonyms(), path, metadata=self.metadata, **kwargs)

    def make_grounder(self, **kwargs: Any) -> Grounder:
        """Get a grounder from all positive synonyms."""
        return make_grounder(self.get_positive_synonyms(), **kwargs)
