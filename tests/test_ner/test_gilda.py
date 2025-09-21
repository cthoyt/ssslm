"""Tests for Gilda."""

from ssslm import literal_mappings_to_gilda
from ssslm.ner import GildaGrounder
from tests import cases
from tests.cases import ALZHEIMER_REFERENCE, LM_1, LM_2, LM_3


@cases.REQUIRES_GILDA
class GildaTestCase(cases.BaseNERTestCase):
    """Test Gilda."""

    def test_gilda(self) -> None:
        """Test Gilda NER."""
        import gilda

        # turns out that LM3 is required to get this to work since the
        # prefix index is case-sensitive
        terms = literal_mappings_to_gilda([LM_1, LM_2, LM_3])
        mock_gilda_grounder: gilda.Grounder = gilda.make_grounder(terms)

        grounder = GildaGrounder(mock_gilda_grounder)

        # note https://github.com/gyorilab/gilda/blob/3dcaf39c4bf77823db5f3012856cb2115beeb3c9/gilda/ner.py#L134-L137
        # has a known error that will fail for Alzheimer's disease with a quote
        for t in ["alzheimer disease", "Alzheimer disease"]:
            match = grounder.get_best_match(t)
            if match is None:
                self.fail(msg=f"could not ground {t}")
            self.assertEqual(ALZHEIMER_REFERENCE, match.reference)

        self.assert_ner_alzheimer(grounder)
