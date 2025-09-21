"""Tests for pandas integration."""

import unittest

from curies import NamedReference

from ssslm import Match, make_grounder
from ssslm.model import PANDAS_AVAILABLE, LiteralMapping


@unittest.skipUnless(PANDAS_AVAILABLE, reason="This test requires pandas")
class TestPandas(unittest.TestCase):
    """Tests for pandas integration."""

    def test_ground_df(self) -> None:
        """Test grounding a dataframe."""
        import pandas as pd

        text = "test"
        reference = NamedReference.from_curie("sgd:S000000019", name="YAL021C")
        literal_mappings = [LiteralMapping(reference=reference, text=text)]

        grounder = make_grounder(literal_mappings)

        column = "gene"
        columns = [column]
        rows = [
            (None,),
            ("nope",),
            (text,),
        ]
        df = pd.DataFrame(rows, columns=columns)

        grounder.ground_df(df, column, target_column="test1")
        grounder.ground_df(df, column, target_column="test2", target_type="curie")
        grounder.ground_df(
            df,
            column,
            target_column="test3",
            target_type="reference",
        )
        grounder.ground_df(
            df,
            column,
            target_column="test4",
            target_type="match",
        )

        with self.assertRaises(KeyError):
            grounder.ground_df(
                df,
                column,
                target_type="nope",
            )

        self.assertEqual(
            [
                [None, None, None, None, None],
                ["nope", None, None, None, None],
                [
                    text,
                    reference.curie,
                    reference.curie,
                    reference,
                    Match(reference=reference, score=5 / 9),
                ],
            ],
            df.values.tolist(),
        )
