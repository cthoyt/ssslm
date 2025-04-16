Named Entity Recognition
========================

The SSSLM software package contains a submodule :mod:`ssslm.ner` for named entity
recognition (NER) and named entity normalization (NEN) that provides a standard class
API and data model encoded with :mod:`pydantic` models.

Case Study 1
------------

In the following example, we load a pre-constructed lexicon for diseases and phenotypes
from the Biolexica project. We then apply it to a small table from the OBO Academy's
tutorial `From Tables to Linked Data
<https://oboacademy.github.io/obook/tutorial/linking-data/>`_ to demonstrate grounding.

The initial table looks like this:

======= ======= ==============
species strain  disease
======= ======= ==============
RAT     F 344/N ADENOCARCINOMA
MOUSE   B6C3F1  INFLAMMATION
RAT     F 344/N NECROSIS
======= ======= ==============

Our goal is to look up the best possible ontology/database identifiers for diseases in
the second-to-last column. The following code accomplishes this in two different
flavors:

1. By adding a column ``disease_curie`` that contains string representations of the
   references to external ontologies like the Disease Ontology (DOID) and Symptom
   Ontology (SYMP).
2. By adding a column ``disease_reference`` that contains a data structure with the
   prefix, identifier, and name of the references.

.. code-block:: python

    import pandas as pd
    import ssslm

    INDEX = "phenotype"
    mappings_url = f"https://github.com/biopragmatics/biolexica/raw/main/lexica/{INDEX}/{INDEX}.ssslm.tsv.gz"

    grounder = ssslm.make_grounder(mappings_url)

    data_url = "https://raw.githubusercontent.com/OBOAcademy/obook/master/docs/tutorial/linking_data/data.csv"
    df = pd.read_csv(data_url)
    df = df[["species", "strain", "disease"]]
    print(df.to_markdown(tablefmt="rst", index=False))

    # this adds a new column `disease_curie` that has strings
    # for the Bioregistry-standardized CURIEs
    grounder.ground_pandas_df(df, "disease", target_column="disease_curie")

    # this adds a new column `disease_curie` that has reference objects
    # for Bioregistry-standardized references (e.g., pre-parsed prefix, identifier, and name)
    grounder.ground_pandas_df(
        df, "disease", target_column="disease_reference", target_type="reference"
    )

    print(df.to_markdown(tablefmt="rst", index=False))

Here's what it looks like in the end:

======= ======= ============== ============= ==================================
species strain  disease        disease_curie disease_reference
======= ======= ============== ============= ==================================
RAT     F 344/N ADENOCARCINOMA doid:299      prefix='doid' identifier='299'
                                             name='adenocarcinoma'
MOUSE   B6C3F1  INFLAMMATION   symp:0000061  prefix='symp' identifier='0000061'
                                             name='inflammation'
RAT     F 344/N NECROSIS       symp:0000132  prefix='symp' identifier='0000132'
                                             name='necrosis'
======= ======= ============== ============= ==================================
