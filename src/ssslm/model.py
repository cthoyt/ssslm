"""A data model for synonyms."""

from __future__ import annotations

import builtins
import csv
import datetime
import gzip
import importlib.util
import itertools as itt
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, Literal, NamedTuple, TypeAlias, cast, overload

from curies import NamableReference, Reference, ReferenceTuple
from curies import vocabulary as v
from pydantic import BaseModel, Field
from pydantic_extra_types.language_code import LanguageAlpha2
from pystow.utils import safe_open, safe_open_writer
from tqdm import tqdm
from typing_extensions import TypeVar

if TYPE_CHECKING:
    import gilda
    import pandas

__all__ = [
    "DEFAULT_PREDICATE",
    "PREDICATES",
    "GildaErrorPolicy",
    "LiteralMapping",
    "LiteralMappingIndex",
    "LiteralMappingTuple",
    "R",
    "Writer",
    "append_literal_mapping",
    "df_to_literal_mappings",
    "get_prefixes",
    "group_literal_mappings",
    "lint_literal_mappings",
    "literal_mappings_to_df",
    "literal_mappings_to_gilda",
    "read_gilda_terms",
    "read_literal_mappings",
    "remap_literal_mappings",
    "write_gilda_terms",
    "write_literal_mappings",
]

PANDAS_AVAILABLE = importlib.util.find_spec("pandas")
GILDA_AVAILABLE = importlib.util.find_spec("gilda")

R = TypeVar("R", bound=NamableReference, default=NamableReference)


class LiteralMappingTuple(NamedTuple):
    """Represents rows in a spreadsheet."""

    text: str
    curie: str
    name: str | None
    predicate: str
    type: str | None
    provenance: str | None
    contributor: str | None
    date: str | None
    language: str | None
    comment: str | None
    source: str | None
    taxon: str | None


SynonymTuple = LiteralMappingTuple
NamableReferenceType: TypeAlias = type[NamableReference]

#: The header for the spreadsheet
HEADER = list(LiteralMappingTuple._fields)

#: A set of permissible predicates
PREDICATES = [v.has_label, *v.synonym_scopes.values()]

#: The default synonym type predicate was chosen based on the OBO
#: standard - when you don't specify a scope, this is what it infers
DEFAULT_PREDICATE = v.has_related_synonym

#: The error policy when converting to/from gilda terms
GildaErrorPolicy: TypeAlias = Literal["ignore", "raise"]


class LiteralMapping(BaseModel, Generic[R]):
    """A data model for literal mappings."""

    # the first four fields are the core of the literal mapping
    reference: R = Field(..., description="The subject of the literal mapping")
    predicate: Reference = Field(
        default=DEFAULT_PREDICATE,
        description="The predicate that connects the term (as subject) "
        "to the textual synonym (as object)",
        examples=PREDICATES,
    )
    text: str = Field(..., description="The object of the literal mapping")
    language: LanguageAlpha2 | None = Field(
        None,
        description="The language of the synonym. If not given, typically "
        "assumed to be american english.",
    )

    type: Reference | None = Field(
        default=None,
        title="Synonym type",
        description="A qualification for the type of mapping",
        examples=list(v.synonym_types),
    )
    provenance: list[Reference] = Field(
        default_factory=list,
        description="A list of articles (e.g., from PubMed, PMC, arXiv) where this synonym appears",
    )
    contributor: Reference | None = Field(
        None,
        description="The contributor, usually given as a reference to ORCID",
        examples=[v.charlie],
    )
    comment: str | None = Field(
        None, description="An optional comment on the synonym curation or status"
    )
    source: str | None = Field(
        None, description="The name of the resource where the synonym was curated"
    )
    date: datetime.date | None = Field(None, description="The date of initial curation")
    taxon: Reference | None = Field(
        None,
        description="If taxon-specific, annotate it here. "
        "Only use `NCBITaxon` or `ncbitaxon` as the prefix.",
    )

    def __lt__(self, other: LiteralMapping[R]) -> bool:
        return _lm_sort_key(self) < _lm_sort_key(other)

    def get_all_references(self) -> set[Reference]:
        """Get all references made by this object."""
        rv: set[Reference] = {self.reference, self.predicate, *self.provenance}
        if self.type:
            rv.add(self.type)
        if self.contributor:
            rv.add(self.contributor)
        return rv

    @property
    def name(self) -> str | None:
        """Get the reference's (optional) name."""
        return self.reference.name

    @property
    def curie(self) -> str:
        """Get the reference's CURIE."""
        return self.reference.curie

    @property
    def date_str(self) -> str:
        """Get the date as a string."""
        if self.date is None:
            raise ValueError("date is not set")
        return self.date.strftime("%Y-%m-%d")

    # docstr-coverage:excused `overload`
    @overload
    @classmethod
    def from_row(
        cls,
        row: dict[str, Any],
        *,
        names: Mapping[Reference, str] | None = ...,
        reference_cls: builtins.type[R] = ...,
    ) -> LiteralMapping[R]: ...

    # docstr-coverage:excused `overload`
    @overload
    @classmethod
    def from_row(
        cls,
        row: dict[str, Any],
        *,
        names: Mapping[Reference, str] | None = ...,
        reference_cls: None = ...,
    ) -> LiteralMapping[NamableReference]: ...

    @classmethod
    def from_row(
        cls,
        row: dict[str, Any],
        *,
        names: Mapping[Reference, str] | None = None,
        reference_cls: builtins.type[R] | None = None,
    ) -> LiteralMapping[R] | LiteralMapping[NamableReference]:
        """Parse a dictionary representing a row in a TSV."""
        if reference_cls is None:
            reference_cls = NamableReference  # type:ignore
        assert reference_cls is not None  # noqa:S101
        reference = NamableReference.from_curie(row["curie"])
        name = (names or {}).get(reference) or row.get("name")
        data = {
            "text": row["text"],
            "reference": reference_cls(
                prefix=reference.prefix, identifier=reference.identifier, name=name
            ),
            "predicate": (
                reference_cls.from_curie(predicate_curie.strip())
                if (predicate_curie := row.get("predicate"))
                else DEFAULT_PREDICATE
            ),
            "provenance": [
                reference_cls.from_curie(provenance_curie.strip())
                for provenance_curie in (row.get("provenance") or "").split(",")
                if provenance_curie.strip()
            ],
            # get("X") or None protects against empty strings
            "type": row.get("type") or None,
            "language": row.get("language") or None,
            "comment": row.get("comment") or None,
            "source": row.get("source") or None,
            "date": row.get("date") or None,
        }
        if contributor_curie := (row.get("contributor") or "").strip():
            data["contributor"] = reference_cls.from_curie(contributor_curie)

        return cast(LiteralMapping[NamableReference], cls.model_validate(data))

    def _as_row(self) -> LiteralMappingTuple:
        """Get the synonym as a row for writing."""
        return LiteralMappingTuple(
            text=self.text,
            curie=self.curie,
            name=self.name,
            predicate=self.predicate.curie,
            type=self.type.curie if self.type else None,
            provenance=",".join(p.curie for p in self.provenance) if self.provenance else None,
            contributor=self.contributor.curie if self.contributor is not None else None,
            date=self.date_str if self.date is not None else None,
            language=self.language or None,
            comment=self.comment or None,
            source=self.source or None,
            taxon=self.taxon.curie if self.taxon else None,
        )

    def _as_row_for_writer(self) -> Sequence[str]:
        return tuple(x or "" for x in self._as_row())

    @staticmethod
    def _predicate_type_from_gilda(status: GildaStatus) -> tuple[Reference, Reference | None]:
        if status == "name":
            return v.has_label, None
        elif status == "former_name":
            return DEFAULT_PREDICATE, v.previous_name
        elif status == "synonym":
            return DEFAULT_PREDICATE, None
        elif status == "curated":
            # assume higher confidence in exact synonym
            return v.has_exact_synonym, None
        raise ValueError(f"unhandled gilda status: {status}")

    # docstr-coverage:excused `overload`
    @overload
    @classmethod
    def from_gilda(
        cls, term: gilda.Term, *, reference_cls: builtins.type[R] = ...
    ) -> LiteralMapping[R]: ...

    # docstr-coverage:excused `overload`
    @overload
    @classmethod
    def from_gilda(
        cls, term: gilda.Term, *, reference_cls: None = ...
    ) -> LiteralMapping[NamableReference]: ...

    @classmethod
    def from_gilda(
        cls, term: gilda.Term, *, reference_cls: builtins.type[R] | None = None
    ) -> LiteralMapping[R] | LiteralMapping[NamableReference]:
        """Construct a synonym from a :mod:`gilda` term.

        :param term: A Gilda term
        :param reference_cls: the class to use to instantiate references

        :returns: A literal mapping object

        .. warning::

            Gilda's data model is less detailed, so resulting synonym objects will not
            have detailed curation provenance
        """
        if reference_cls is None:
            reference_cls = NamableReference  # type:ignore
        assert reference_cls is not None  # noqa:S101
        predicate, synonym_type = cls._predicate_type_from_gilda(term.status)
        data = {
            "reference": reference_cls(prefix=term.db, identifier=term.id, name=term.entry_name),
            "predicate": predicate,
            "text": term.text,
            "type": synonym_type,
            "source": term.source,
        }
        if term.organism:
            data["taxon"] = reference_cls(prefix="NCBITaxon", identifier=term.organism)
        return cast(LiteralMapping[NamableReference], cls.model_validate(data))

    def _get_gilda_status(self) -> GildaStatus:
        """Get the Gilda status for a synonym."""
        if self.predicate and self.predicate.pair == v.has_label.pair:
            return "name"
        if self.type and self.type.pair == v.previous_name.pair:
            return "former_name"
        return "synonym"

    def to_gilda(self) -> gilda.Term:
        """Get this synonym as a :mod:`gilda` term.

        :returns: An object that can be indexed by Gilda for NER and grounding
        """
        if not self.name:
            raise ValueError(f"can't make a Gilda term without a label for {self.reference.pair}")
        if self.taxon and self.taxon.prefix.lower() != "ncbitaxon":
            raise ValueError("NCBITaxon reference is required to convert to gilda.")
        return _gilda_term(
            text=self.text,
            reference=self.reference,
            status=self._get_gilda_status(),
            source=self.source or self.reference.prefix,
            ncbitaxon_id=self.taxon.identifier if self.taxon else None,
        )


#: An index from the reference to a list of mappings that use the reference
LiteralMappingIndex: TypeAlias = dict[R, list[LiteralMapping[R]]]


def literal_mappings_to_gilda(
    literal_mappings: Iterable[LiteralMapping[R]], *, on_error: GildaErrorPolicy = "raise"
) -> list[gilda.Term]:
    """Convert literal mappings to gilda terms."""
    gilda_terms = []
    for literal_mapping in literal_mappings:
        try:
            gilda_term = literal_mapping.to_gilda()
        except ValueError:
            if on_error == "raise":
                raise
        else:
            gilda_terms.append(gilda_term)
    return gilda_terms


#: See https://github.com/gyorilab/gilda/blob/ea328734f26c91189438e6d3408562f990f38644/gilda/term.py#L167C1-L167C69
GildaStatus: TypeAlias = Literal["name", "synonym", "curated", "former_name"]


def _gilda_term(
    *,
    text: str,
    reference: NamableReference,
    status: GildaStatus,
    source: str | None,
    ncbitaxon_id: str | None = None,
) -> gilda.Term:
    import gilda
    from gilda.process import normalize

    norm_text = normalize(text)  # type:ignore[no-untyped-call]

    return gilda.Term(  # type:ignore[no-untyped-call]
        norm_text,
        text=text,
        db=reference.prefix,
        id=reference.identifier,
        entry_name=reference.name or text,
        status=status,
        source=source,
        organism=ncbitaxon_id,
    )


def literal_mappings_to_df(literal_mappings: Iterable[LiteralMapping[R]]) -> pandas.DataFrame:
    """Get a pandas dataframe from the literal mappings."""
    import pandas as pd

    df = pd.DataFrame(
        (literal_mapping._as_row() for literal_mapping in literal_mappings), columns=HEADER
    )

    # remove any columns that are fully blank
    for col in df.columns:
        if df[col].isna().all():
            del df[col]

    return df


# docstr-coverage:excused `overload`
@overload
def df_to_literal_mappings(
    df: pandas.DataFrame,
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: None = ...,
) -> list[LiteralMapping[NamableReference]]: ...


# docstr-coverage:excused `overload`
@overload
def df_to_literal_mappings(
    df: pandas.DataFrame,
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: type[R] = ...,
) -> list[LiteralMapping[R]]: ...


def df_to_literal_mappings(
    df: pandas.DataFrame,
    *,
    names: Mapping[Reference, str] | None = None,
    reference_cls: type[R] | None = None,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    """Get mapping objects from a dataframe."""
    it = (row for _, row in df.iterrows())
    if reference_cls is None:
        return _from_dicts(it, names=names)
    else:
        return _from_dicts(it, names=names, reference_cls=reference_cls)


#: Valid writers
Writer = Literal["pandas", "csv"]


def _resolve_writer(writer: Writer | None = None) -> Writer:
    if writer is None or writer == "pandas":
        if PANDAS_AVAILABLE:
            return "pandas"
        else:
            return "csv"
    return writer


def write_literal_mappings(
    literal_mappings: Iterable[LiteralMapping[R]],
    path: str | Path,
    *,
    writer: Writer | None = None,
) -> None:
    """Write literal mappings to a path."""
    path = Path(path).expanduser().resolve()
    writer = _resolve_writer(writer)
    if writer == "pandas":
        _write_pandas(literal_mappings=literal_mappings, path=path)
    elif writer == "csv":
        _write_builtin(literal_mappings=literal_mappings, path=path)
    else:
        raise ValueError(f"invalid writer: {writer}. Choose one of {Writer}")


def _write_builtin(*, path: Path, literal_mappings: Iterable[LiteralMapping[R]]) -> None:
    with safe_open_writer(path) as writer:
        writer.writerow(HEADER)
        writer.writerows(
            literal_mapping._as_row_for_writer() for literal_mapping in literal_mappings
        )


def _write_pandas(*, path: Path, literal_mappings: Iterable[LiteralMapping[R]]) -> None:
    df = literal_mappings_to_df(literal_mappings)
    df.to_csv(path, index=False, sep="\t")


def append_literal_mapping(literal_mapping: LiteralMapping[R], path: str | Path) -> None:
    """Append a literal mapping to an existing file."""
    with Path(path).expanduser().resolve().open("a") as file:
        print(*literal_mapping._as_row_for_writer(), sep="\t", file=file)


# docstr-coverage:excused `overload`
@overload
def read_literal_mappings(
    path: str | Path,
    *,
    delimiter: str | None = ...,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: type[R] = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[R]]: ...


# docstr-coverage:excused `overload`
@overload
def read_literal_mappings(
    path: str | Path,
    *,
    delimiter: str | None = ...,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: None = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[NamableReference]]: ...


def read_literal_mappings(
    path: str | Path,
    *,
    delimiter: str | None = None,
    names: Mapping[Reference, str] | None = None,
    reference_cls: type[R] | None = None,
    show_progress: bool = False,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    """Load literal mappings from a file.

    :param path: A local file path or URL for a biosynonyms-flavored CSV/TSV file
    :param delimiter: The delimiter for the CSV/TSV file. Defaults to tab
    :param names: A pre-parsed dictionary from references (i.e., prefix-luid pairs) to
        default labels
    :param reference_cls: The class used to parse references. E.g., swap out for
        :class:`pyobo.Reference` to automatically do Bioregistry validation on
        references.
    :param show_progress: Should a progress bar be shown? Defaults to false.

    :returns: A list of literal mappings parsed from the table
    """
    if reference_cls is None:
        reference_cls = NamableReference  # type:ignore
    assert reference_cls is not None  # noqa:S101

    if isinstance(path, str) and any(path.startswith(schema) for schema in ("https://", "http://")):
        import requests

        if path.endswith(".gz"):
            with requests.get(path, stream=True, timeout=15) as res:
                lines = gzip.decompress(res.content).decode().splitlines()
                return _from_lines(
                    lines,
                    delimiter=delimiter,
                    names=names,
                    reference_cls=reference_cls,
                    show_progress=show_progress,
                )
        else:
            res = requests.get(path, timeout=15)
            res.raise_for_status()
            return _from_lines(
                res.iter_lines(decode_unicode=True),
                delimiter=delimiter,
                names=names,
                reference_cls=reference_cls,
                show_progress=show_progress,
            )

    path = Path(path).expanduser().resolve()

    if path.suffix == ".numbers":
        return _parse_numbers(
            path, names=names, show_progress=show_progress, reference_cls=reference_cls
        )

    with safe_open(path) as file:
        return _from_lines(
            file,
            delimiter=delimiter,
            names=names,
            reference_cls=reference_cls,
            show_progress=show_progress,
        )


# docstr-coverage:excused `overload`
@overload
def read_gilda_terms(
    path: str | Path,
    *,
    reference_cls: type[R] = ...,
) -> list[LiteralMapping[R]]: ...


# docstr-coverage:excused `overload`
@overload
def read_gilda_terms(
    path: str | Path,
    *,
    reference_cls: None = ...,
) -> list[LiteralMapping[NamableReference]]: ...


def read_gilda_terms(
    path: str | Path,
    *,
    reference_cls: type[R] | None = None,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    """Read Gilda terms from a file."""
    import gilda.grounder

    path = _prepare_gilda_path(path)

    # we know the result will be homogenous, so we ignore
    return [  # type:ignore[return-value]
        LiteralMapping.from_gilda(gilda_term, reference_cls=reference_cls)
        for gilda_term in gilda.grounder.load_entries_from_terms_file(path)
    ]


def write_gilda_terms(
    literal_mappings: Iterable[LiteralMapping[R]],
    path: str | Path,
    *,
    on_error: GildaErrorPolicy = "ignore",
) -> None:
    """Write Gilda terms to a file."""
    from gilda import dump_terms

    path = _prepare_gilda_path(path)
    dump_terms(literal_mappings_to_gilda(literal_mappings, on_error=on_error), path)


def _prepare_gilda_path(path: str | Path) -> Path:
    path = Path(path).expanduser().resolve()
    if not path.suffix.endswith(".gz"):
        raise ValueError(f"gilda terms files are required to be gzipped and end with .gz: {path}")
    return path


# docstr-coverage:excused `overload`
@overload
def _parse_numbers(
    path: str | Path,
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: None = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[NamableReference]]: ...


# docstr-coverage:excused `overload`
@overload
def _parse_numbers(
    path: str | Path,
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: type[R] = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[R]]: ...


def _parse_numbers(
    path: str | Path,
    *,
    names: Mapping[Reference, str] | None = None,
    reference_cls: type[R] | None = None,
    show_progress: bool = False,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    # code example from https://pypi.org/project/numbers-parser
    import numbers_parser

    doc = numbers_parser.Document(path)
    sheets = doc.sheets
    tables = sheets[0].tables
    header, *rows = tables[0].rows(values_only=True)
    return _from_dicts(
        (dict(zip(header, row, strict=False)) for row in rows),
        names=names,
        reference_cls=reference_cls,
        show_progress=show_progress,
    )


# docstr-coverage:excused `overload`
@overload
def _from_lines(
    lines: Iterable[str],
    *,
    delimiter: str | None = ...,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: None = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[NamableReference]]: ...


# docstr-coverage:excused `overload`
@overload
def _from_lines(
    lines: Iterable[str],
    *,
    delimiter: str | None = ...,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: type[R] = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[R]]: ...


def _from_lines(
    lines: Iterable[str],
    *,
    delimiter: str | None = None,
    names: Mapping[Reference, str] | None = None,
    reference_cls: type[R] | None = None,
    show_progress: bool = False,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    return _from_dicts(
        csv.DictReader(lines, delimiter=delimiter or "\t"),
        names=names,
        reference_cls=reference_cls,
        show_progress=show_progress,
    )


# docstr-coverage:excused `overload`
@overload
def _from_dicts(
    dicts: Iterable[dict[str, Any]],
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: None = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[NamableReference]]: ...


# docstr-coverage:excused `overload`
@overload
def _from_dicts(
    dicts: Iterable[dict[str, Any]],
    *,
    names: Mapping[Reference, str] | None = ...,
    reference_cls: type[R] = ...,
    show_progress: bool = ...,
) -> list[LiteralMapping[R]]: ...


def _from_dicts(
    dicts: Iterable[dict[str, Any]],
    *,
    names: Mapping[Reference, str] | None = None,
    reference_cls: type[R] | None = None,
    show_progress: bool = False,
) -> list[LiteralMapping[R]] | list[LiteralMapping[NamableReference]]:
    rv = []
    it = tqdm(
        dicts,
        unit_scale=True,
        unit="mapping",
        desc="parsing literal mappings",
        disable=not show_progress,
    )
    for i, record in enumerate(it, start=2):
        record = {
            k: v
            for k, v in record.items()
            if k and v and isinstance(v, str) and k.strip() and v.strip()
        }
        if record:
            try:
                literal_mapping = LiteralMapping.from_row(
                    record, names=names, reference_cls=reference_cls
                )
            except ValueError as e:
                raise ValueError(f"failed on row {i}: {record}") from e
            rv.append(literal_mapping)
    # ignore here since we know that the types will be homogenous
    return rv  # type:ignore[return-value]


def group_literal_mappings(
    literal_mappings: Iterable[LiteralMapping[R]],
) -> dict[R, list[LiteralMapping[R]]]:
    """Aggregate literal mappings by reference."""
    dd: defaultdict[R, list[LiteralMapping[R]]] = defaultdict(list)
    for literal_mapping in tqdm(
        literal_mappings, unit="literal mapping", unit_scale=True, leave=False
    ):
        dd[literal_mapping.reference].append(literal_mapping)
    return dict(dd)


def get_prefixes(
    literal_mapping_index: LiteralMappingIndex[R] | list[LiteralMapping[R]],
) -> set[str]:
    """Get all prefixes appearing in a literal mapping index or iterable of literal mappings."""
    if isinstance(literal_mapping_index, dict):
        return _get_prefixes_from_index(literal_mapping_index)
    elif isinstance(literal_mapping_index, list):
        return _get_prefixes_from_iterable(literal_mapping_index)
    else:
        raise TypeError


def _get_prefixes_from_iterable(literal_mappings: Iterable[LiteralMapping[R]]) -> set[str]:
    return {
        reference.prefix
        for literal_mapping in literal_mappings
        for reference in literal_mapping.get_all_references()
    }


def _get_prefixes_from_index(literal_mapping_index: LiteralMappingIndex[R]) -> set[str]:
    return _get_prefixes_from_iterable(
        literal_mapping
        for literal_mappings in literal_mapping_index.values()
        for literal_mapping in literal_mappings
    )


def lint_literal_mappings(
    path: Path,
    *,
    delimiter: str | None = None,
    reference_cls: type[R] | None = None,
) -> None:
    """Lint a literal mappings file."""
    literal_mappings = read_literal_mappings(path, delimiter=delimiter, reference_cls=reference_cls)
    literal_mappings = sorted(literal_mappings)  # type:ignore[assignment]
    # it's okay the type can't be ignored for this, since it doesn't matter what it is
    write_literal_mappings(literal_mappings, path)  # type:ignore[misc]


def _lm_sort_key(lm: LiteralMapping[R]) -> tuple[str, str, str, str]:
    return lm.text.casefold(), lm.text, lm.reference.curie.casefold(), lm.reference.curie


def remap_literal_mappings(
    literal_mappings: list[LiteralMapping[R]],
    mappings: list[tuple[R, R]],
    *,
    progress: bool = False,
) -> list[LiteralMapping[R]]:
    """Use a priority mapping to re-write terms with priority groundings.

    :param literal_mappings: A list of literal mappings
    :param mappings: A list of pairs that constitute mappings, e.g. from SeMRA
    :param progress: Should a progress bar be shown?

    :returns: A new list of literal mapping objects that have been remapped
    """
    index = group_literal_mappings(literal_mappings)

    # build a lookup table, since the mappings coming into this function
    # might not have names associated with them, but the literal mappings do
    refs: dict[ReferenceTuple, R] = {i.pair: i for i in index}

    for source, target in tqdm(
        mappings, unit="mapping", unit_scale=True, desc="applying mappings", disable=not progress
    ):
        # overwrite the target with a reference that has a name, if it exists
        target = refs.get(target.pair, target)
        source_literal_mappings: list[LiteralMapping[R]] | None = index.pop(source, None)
        if source_literal_mappings:
            index.setdefault(target, []).extend(
                _make_new_lm(literal_mapping, target) for literal_mapping in source_literal_mappings
            )

    # Unwind the terms index
    new_terms = list(itt.chain.from_iterable(index.values()))
    # TODO filter out duplicates?
    return new_terms


def _make_new_lm(
    term: LiteralMapping[R],
    reference: Reference,
) -> LiteralMapping[R]:
    """Make a new literal term object by replacing the database, identifier, and name."""
    new_ref: R = term.reference.__class__(
        prefix=reference.prefix,
        identifier=reference.identifier,
        name=getattr(reference, "name", None),
    )
    return term.model_copy(update={"reference": new_ref})
