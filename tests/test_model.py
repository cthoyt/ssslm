"""Test the data model."""

import datetime
import tempfile
import typing
import unittest
from pathlib import Path

import gilda
import responses
from curies import NamableReference, Reference
from curies import vocabulary as v
from pydantic import model_validator

import ssslm
from ssslm.model import DEFAULT_PREDICATE, LiteralMapping, Writer

TR_1 = NamableReference.from_curie("test:1", "test")
TR_2 = NamableReference.from_curie("test:2", "test2")
TR_3 = NamableReference.from_curie("test:3", "test3")
TR_4 = NamableReference.from_curie("test:4", "test4")
TR_5 = NamableReference.from_curie("test:5", "test5")


def _s(r: Reference) -> Reference:
    return Reference(prefix=r.prefix, identifier=r.identifier)


class TestGildaIO(unittest.TestCase):
    """Test converting between the SSSLM literal mapping data structure and :class:`gilda.Term`."""

    def test_error(self) -> None:
        """Test handling an invalid gilda status."""
        with self.assertRaises(ValueError):
            LiteralMapping._predicate_type_from_gilda("nope")

    def test_gilda_missing_name(self) -> None:
        """Test when trying to generate a gilda term with a missing name."""
        literal_mapping = LiteralMapping(
            text="test",
            reference=NamableReference(prefix="test", identifier="1"),
        )
        with self.assertRaises(ValueError):
            literal_mapping.to_gilda()

    def test_bad_organism(self) -> None:
        """Test when trying to generate a gilda term with non-ncbitaxon reference."""
        literal_mapping = LiteralMapping(
            text="test",
            reference=NamableReference(prefix="test", identifier="1", name="test"),
            taxon=Reference(prefix="kegg", identifier="nope"),
        )
        with self.assertRaises(ValueError) as exc:
            literal_mapping.to_gilda()
        self.assertEqual(
            "NCBITaxon reference is required to convert to gilda.", exc.exception.args[0]
        )

    def test_gilda_synonym(self) -> None:
        """Test getting gilda terms."""
        literal_mapping = LiteralMapping(
            text="tests",
            predicate=v.has_exact_synonym,
            type=v.plural_form,
            reference=TR_1,
        )
        gilda_term = literal_mapping.to_gilda()
        self.assertEqual("synonym", gilda_term.status)

        # the predicate and plural form information gets lost in the round trio
        literal_mapping_expected = LiteralMapping(
            text="tests", predicate=DEFAULT_PREDICATE, reference=TR_1, source=TR_1.prefix
        )
        self.assertEqual(literal_mapping_expected, LiteralMapping.from_gilda(gilda_term))

    def test_gilda_has_taxon(self) -> None:
        """Test getting gilda terms."""
        literal_mapping = LiteralMapping(
            text="tests", reference=TR_1, taxon=Reference(prefix="NCBITaxon", identifier="9606")
        )
        gilda_term = literal_mapping.to_gilda()
        self.assertEqual("synonym", gilda_term.status)

        self.assertEqual(
            literal_mapping.model_copy(update={"source": TR_1.prefix}),
            LiteralMapping.from_gilda(gilda_term),
        )

    def test_gilda_name(self) -> None:
        """Test getting gilda terms."""
        literal_mapping = LiteralMapping(text="test", predicate=v.has_label, reference=TR_1)
        gilda_term = literal_mapping.to_gilda()
        self.assertEqual("name", gilda_term.status)

        self.assertEqual(
            literal_mapping.model_copy(update={"source": TR_1.prefix}),
            LiteralMapping.from_gilda(gilda_term),
        )

    def test_gilda_former_name(self) -> None:
        """Test getting gilda terms."""
        literal_mapping = LiteralMapping(
            text="old test",
            predicate=v.has_exact_synonym,
            reference=TR_1,
            type=v.previous_name,
        )
        gilda_term = literal_mapping.to_gilda()
        self.assertEqual("former_name", gilda_term.status)

        # the predicate gets lost in round trip
        literal_mapping_expected = LiteralMapping(
            text="old test",
            predicate=DEFAULT_PREDICATE,
            type=v.previous_name,
            reference=TR_1,
            source=TR_1.prefix,  # automtically set
        )
        self.assertEqual(literal_mapping_expected, LiteralMapping.from_gilda(gilda_term))

    def test_gilda_curated(self) -> None:
        """Test getting gilda terms."""
        term = gilda.Term(
            "text",
            text="text",
            db="test",
            id="1",
            entry_name="test",
            status="curated",
            source="charlie",
        )
        literal_mapping = LiteralMapping.from_gilda(term)
        self.assertEqual(v.has_exact_synonym, literal_mapping.predicate)


class TestModel(unittest.TestCase):
    """Test the data model."""

    def test_date(self) -> None:
        """Test getting the date."""
        today = datetime.date.today()

        lm1 = LiteralMapping(reference=TR_1, text="test", date=today)
        self.assertIsInstance(lm1.date_str, str)

        lm2 = LiteralMapping(reference=TR_1, text="test")
        with self.assertRaises(ValueError):
            lm2.date_str  # noqa:B018

    def test_get_references(self) -> None:
        """Test getting references."""
        lm1 = LiteralMapping(reference=TR_1, text="test", predicate=v.has_label)
        self.assertEqual({TR_1, v.has_label}, lm1.get_all_references())

        lm2 = LiteralMapping(
            reference=TR_1,
            text="tests",
            predicate=v.has_exact_synonym,
            type=v.plural_form,
        )
        self.assertEqual({TR_1, v.has_exact_synonym, v.plural_form}, lm2.get_all_references())

        lm3 = LiteralMapping(reference=TR_1, text="tests", contributor=v.charlie)
        self.assertEqual({TR_1, DEFAULT_PREDICATE, v.charlie}, lm3.get_all_references())

        provenance = [Reference(prefix="x", identifier=f"{i}") for i in range(2)]
        lm4 = LiteralMapping(
            reference=TR_1,
            text="tests",
            provenance=provenance,
        )
        self.assertEqual({TR_1, DEFAULT_PREDICATE, *provenance}, lm4.get_all_references())

    def test_resolve_writer(self) -> None:
        """Test resolving the writer."""

    def test_io_roundtrip(self) -> None:
        """Test IO roundtrip."""
        today = datetime.date.today()
        literal_mappings = [
            LiteralMapping(reference=TR_1, text="test", predicate=v.has_label, date=today),
            LiteralMapping(
                reference=TR_1,
                text="tests",
                predicate=v.has_exact_synonym,
                type=v.plural_form,
            ),
            LiteralMapping(
                reference=TR_1,
                text="checks",
                predicate=v.has_exact_synonym,
                contributor=v.charlie,
            ),
        ]

        # test pandas round trip
        df = ssslm.literal_mappings_to_df(literal_mappings)
        reconstituted = ssslm.df_to_literal_mappings(df)
        self.assertEqual(literal_mappings, reconstituted)

        for writer in typing.get_args(Writer):
            # test writing/reading round trip
            with tempfile.TemporaryDirectory() as d:
                path = Path(d).joinpath(f"test_{writer}.tsv")
                ssslm.write_literal_mappings(literal_mappings, path, writer=writer)
                reloaded_synonyms = ssslm.read_literal_mappings(path)

            self.assertEqual(literal_mappings, reloaded_synonyms)

        with self.assertRaises(ValueError):
            ssslm.write_literal_mappings(literal_mappings, path, writer="nope")

    def test_gilda_io_roundtrip(self) -> None:
        """Test gilda roundtrip."""
        literal_mappings = [
            LiteralMapping(reference=TR_1, text="test", predicate=v.has_label),
            LiteralMapping(reference=TR_1, text="tests"),
            LiteralMapping(reference=TR_1, text="checks"),
        ]
        # gilda roundtrip makes a few minor changes
        expected_mappings = [
            LiteralMapping(reference=TR_1, text="test", predicate=v.has_label, source=TR_1.prefix),
            LiteralMapping(reference=TR_1, text="tests", source=TR_1.prefix),
            LiteralMapping(reference=TR_1, text="checks", source=TR_1.prefix),
        ]

        # test error on filepath without gz extension
        with self.assertRaises(ValueError):
            ssslm.write_gilda_terms(literal_mappings, Path("terms.tsv"))

        with tempfile.TemporaryDirectory() as d:
            path = Path(d).joinpath("terms.tsv.gz")
            ssslm.write_gilda_terms(literal_mappings, path)

            reloaded = ssslm.read_gilda_terms(path)
            self.assertEqual(expected_mappings, reloaded)

    def test_remap(self) -> None:
        """Test remapping."""
        today = datetime.date.today()
        unchanged = LiteralMapping(reference=TR_3, text="bbb", predicate=v.has_label)
        literal_mappings = sorted(
            [
                LiteralMapping(reference=TR_1, text="test", predicate=v.has_label, date=today),
                unchanged,
            ]
        )
        mappings = [(_s(TR_1), _s(TR_2)), (_s(TR_4), _s(TR_5))]
        new_literal_mappings = ssslm.remap_literal_mappings(literal_mappings, mappings)
        expected_literal_mappings = sorted(
            [
                LiteralMapping(reference=TR_2, text="test", predicate=v.has_label, date=today),
                unchanged,
            ]
        )
        self.assertEqual(expected_literal_mappings, new_literal_mappings)

    @responses.activate
    def test_read_remote(self) -> None:
        """Test reading remote."""
        expected_literal_mappings = [
            LiteralMapping(reference=TR_1, text="test", predicate=v.has_label),
        ]
        url = "https://example.com/test.tsv"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.tsv")
            ssslm.write_literal_mappings(expected_literal_mappings, path)
            responses.add(
                responses.GET,
                url,
                path.read_text(),
            )
        literal_mappings = ssslm.read_literal_mappings(url)
        self.assertEqual(expected_literal_mappings, literal_mappings)

    @responses.activate
    def test_read_gz(self) -> None:
        """Test reading remote gzipped-file."""
        expected_literal_mappings = [
            LiteralMapping(reference=TR_1, text="test", predicate=v.has_label),
        ]
        url = "https://example.com/test.tsv.gz"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.tsv.gz")
            ssslm.write_literal_mappings(expected_literal_mappings, path)

            # first, test that reading from path works
            literal_mappings = ssslm.read_literal_mappings(path)
            self.assertEqual(expected_literal_mappings, literal_mappings)

            # then, set up mocking URL for using requests
            responses.add(
                responses.GET,
                url,
                path.read_bytes(),
            )

        literal_mappings = ssslm.read_literal_mappings(url)
        self.assertEqual(expected_literal_mappings, literal_mappings)

    def test_custom_reference_class(self) -> None:
        """Test when using a custom reference class."""

        class CustomReference(NamableReference):
            """A custom reference that checks the prefix."""

            @model_validator(mode="before")
            def validate_identifier(cls, values):  # noqa
                """Validate the identifier."""
                prefix = values["prefix"]
                if prefix not in {"test.custom"}:
                    raise ValueError(f"invalid prefix: {prefix}")
                return values

        expected_literal_mappings = [
            LiteralMapping(reference=NamableReference.from_curie("test:1", "A"), text="A"),
            LiteralMapping(reference=NamableReference.from_curie("test.custom:02", "B"), text="B"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.tsv")
            ssslm.write_literal_mappings(expected_literal_mappings, path)

            with self.assertRaises(ValueError):
                ssslm.read_literal_mappings(path, reference_cls=CustomReference)
