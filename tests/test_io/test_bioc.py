"""Test parsing BioC."""

import tempfile
import unittest
from pathlib import Path

from curies import NamableReference, NamedReference

from ssslm import Annotation, Match
from ssslm.io.bioc import Document, parse_pubtator

test = """\
26094|t|Antihypertensive drugs and depression: a reappraisal.
26094|a|Eighty-nine new referral hypertensive out-patients and 46 new referral non-hypertensive chronically physically ill out-patients completed a mood rating scale at regular intervals for one year. The results showed a high prevalence of depression in both groups of patients, with no preponderance in the hypertensive group. Hypertensive patients with psychiatric histories had a higher prevalence of depression than the comparison patients. This was accounted for by a significant number of depressions occurring in methyl dopa treated patients with psychiatric histories.
26094	27	37	depression	Disease	D003866
26094	79	91	hypertensive	Disease	D006973
26094	129	141	hypertensive	Disease	D006973
26094	287	297	depression	Disease	D003866
26094	355	367	hypertensive	Disease	D006973
26094	375	387	Hypertensive	Disease	D006973
26094	402	413	psychiatric	Disease	D001523
26094	451	461	depression	Disease	D003866
26094	542	553	depressions	Disease	D003866
26094	567	578	methyl dopa	Chemical	D008750
26094	601	612	psychiatric	Disease	D001523
26094	CID	D008750	D003866

354896|t|Lidocaine-induced cardiac asystole.
354896|a|Intravenous administration of a single 50-mg bolus of lidocaine in a 67-year-old man resulted in profound depression of the activity of the sinoatrial and atrioventricular nodal pacemakers. The patient had no apparent associated conditions which might have predisposed him to the development of bradyarrhythmias; and, thus, this probably represented a true idiosyncrasy to lidocaine.
354896	0	9	Lidocaine	Chemical	D008012
354896	18	34	cardiac asystole	Disease	D006323
354896	90	99	lidocaine	Chemical	D008012
354896	142	152	depression	Disease	D003866
354896	331	347	bradyarrhythmias	Disease	D001919
354896	409	418	lidocaine	Chemical	D008012
354896	CID	D008012	D006323
"""  # noqa:E501

TITLE_1 = "Antihypertensive drugs and depression: a reappraisal."
ABSTRACT_1 = "Eighty-nine new referral hypertensive out-patients and 46 new referral non-hypertensive chronically physically ill out-patients completed a mood rating scale at regular intervals for one year. The results showed a high prevalence of depression in both groups of patients, with no preponderance in the hypertensive group. Hypertensive patients with psychiatric histories had a higher prevalence of depression than the comparison patients. This was accounted for by a significant number of depressions occurring in methyl dopa treated patients with psychiatric histories."  # noqa:E501


class BioCTestCase(unittest.TestCase):
    """Test parsing BioC."""

    def test_parse_bioc(self) -> None:
        """Test parsing BioC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir).joinpath("test.txt")
            path.write_text(test)
            documents = list(parse_pubtator(path, prefix="mesh"))

        self.assertEqual(4, len(documents))
        actual_d1, _actual_d2 = documents
        expected_d1 = Document(
            reference=NamedReference(
                prefix="pubmed",
                identifier="26094",
                name="Antihypertensive drugs and depression: a reappraisal.",
            ),
            abstract=ABSTRACT_1,
            annotations=[],
        )
        self.assertEqual(expected_d1.reference, actual_d1.reference)

        self.assertIn(
            Annotation(
                start=79,
                end=91,
                text="hypertensive",
                match=Match(
                    reference=NamableReference(prefix="mesh", identifier="D006973"), score=1.0
                ),
            ),
            actual_d1.annotations,
        )
