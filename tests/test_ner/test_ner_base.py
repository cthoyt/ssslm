"""Tests for NER."""

import tempfile
from pathlib import Path

import curies
from curies import NamedReference, Reference

import ssslm
from ssslm import LiteralMapping
from ssslm.ner import (
    Annotation,
    Match,
    make_grounder,
    read_annotations,
    write_annotations,
)
from tests import cases
from tests.cases import REQUIRES_GILDA


class TestNER(cases.BaseNERTestCase):
    """Test NER."""

    def test_impl_error(self) -> None:
        """Test erroring on invalid impl."""
        with self.assertRaises(ValueError):
            make_grounder([], implementation="xxx")  # type:ignore[arg-type]

    @REQUIRES_GILDA
    def test_grounder(self) -> None:
        """Test getting a grounder from a single reference."""
        import gilda

        text = "test"
        reference = NamedReference.from_curie("sgd:S000000019", name="YAL021C")
        literal_mapping = LiteralMapping(reference=reference, text=text)

        for grounder_cls in [None, gilda.Grounder]:
            with self.subTest(cls=grounder_cls):
                grounder = make_grounder([literal_mapping], grounder_cls=grounder_cls)
                self._assert_grounder(grounder, reference, text)

        # test for making grounder from a file
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.tsv")
            ssslm.write_literal_mappings([literal_mapping], path)
            grounder = make_grounder(path)
            self._assert_grounder(grounder, reference, text)

    def _assert_grounder(self, grounder: ssslm.Grounder, reference: Reference, text: str) -> None:
        self.assertIsNone(grounder.get_best_match("nope"))

        scored_matches = grounder.get_matches(text)
        self.assertEqual(1, len(scored_matches))
        match = scored_matches[0]
        self.assertEqual(reference, match.reference)
        self.assertEqual("sgd", match.prefix)
        self.assertEqual("S000000019", match.identifier)
        self.assertEqual("sgd:S000000019", match.curie)
        self.assertEqual("YAL021C", match.name)

        sentence = f"This sentence is about {text} and all of its great things."
        annotations = grounder.annotate(sentence)
        self.assertEqual(1, len(annotations))
        annotation = annotations[0]
        self.assertEqual(reference, annotation.reference)
        self.assertEqual(sentence, annotation.text)
        self.assertEqual("sgd", annotation.prefix)
        self.assertEqual("S000000019", annotation.identifier)
        self.assertEqual("sgd:S000000019", annotation.curie)
        self.assertEqual(5 / 9, annotation.score)
        self.assertEqual("YAL021C", annotation.name)
        self.assertEqual(text, annotation.substr)

    def test_annotation_io(self) -> None:
        """Test reading and writing annotations."""
        annotation = Annotation(
            match=Match(
                reference=curies.NamableReference(
                    prefix="prefix", identifier="identifier", name="name"
                ),
                score=0.123,
            ),
            start=1,
            end=10,
            text="hello",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).joinpath("test.tsv")
            write_annotations([annotation], path)
            self.assertEqual([annotation], read_annotations(path))
