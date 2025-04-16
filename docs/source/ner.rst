Named Entity Recognition
========================

The SSSLM software package contains a submodule :mod:`ssslm.ner` for named entity
recognition (NER) and named entity normalization (NEN) that provides a standard class
API and data model encoded with :mod:`pydantic` models.

Grounding using pre-constructed lexica
--------------------------------------

In the following example, we load two pre-constructed lexica for diseases/phenotypes and
for anatomical terms from the Biolexica project. By default, SSSLM wraps the NER/NEN
system implemented in :mod:`gilda`, but is exensible for other systems.

We then apply it to a small table from the OBO Academy's tutorial `From Tables to Linked
Data <https://oboacademy.github.io/obook/tutorial/linking-data/>`_ to demonstrate
grounding.

The initial table looks like this:

======= ======= ============== ==============
species strain  organ          disease
======= ======= ============== ==============
RAT     F 344/N LUNG           ADENOCARCINOMA
MOUSE   B6C3F1  NOSE           INFLAMMATION
RAT     F 344/N ADRENAL CORTEX NECROSIS
======= ======= ============== ==============

Our goal is to look up the best possible ontology/database identifiers first for organs
int the second-to-last column then for diseases in the last column. The example code
shows two different flavors of grounding for both entity types:

1. By adding a column ``organ_curie`` that contains string representations of the
   references to external ontologies like the Brenda Tissue Ontology (BTO).
2. By adding a column ``organ_reference`` that contains a data structure with the
   prefix, identifier, and name of the references.
3. By adding a column ``disease_curie`` that contains string representations of the
   references to external ontologies like the Disease Ontology (DOID) and Symptom
   Ontology (SYMP).
4. By adding a column ``disease_reference`` that contains a data structure with the
   prefix, identifier, and name of the references.

.. code-block:: python

    import pandas as pd
    import ssslm

    mappings_fmt = "https://github.com/biopragmatics/biolexica/raw/main/lexica/{key}/{key}.ssslm.tsv.gz"

    phenotype_grounder = ssslm.make_grounder(mappings_fmt.format(key="phenotype"))
    anatomy_grounder = ssslm.make_grounder(mappings_fmt.format(key="anatomy"))

    data_url = "https://raw.githubusercontent.com/OBOAcademy/obook/master/docs/tutorial/linking_data/data.csv"
    df = pd.read_csv(data_url)
    df = df[["species", "strain", "organ", "disease"]]
    print(df.to_markdown(tablefmt="rst", index=False))

    # this adds a new column `organ_curie` that has strings
    # for the Bioregistry-standardized CURIEs
    anatomy_grounder.ground_pandas_df(df, "organ", target_column="organ_curie")

    # this adds a new column `organ_reference` that has reference objects
    # for Bioregistry-standardized references (e.g., pre-parsed prefix, identifier, and name)
    anatomy_grounder.ground_pandas_df(
        df, "organ", target_column="organ_reference", target_type="reference"
    )

    # this adds a new column `disease_curie` that has strings
    # for the Bioregistry-standardized CURIEs
    phenotype_grounder.ground_pandas_df(df, "disease", target_column="disease_curie")

    # this adds a new column `disease_curie` that has reference objects
    # for Bioregistry-standardized references (e.g., pre-parsed prefix, identifier, and name)
    phenotype_grounder.ground_pandas_df(
        df, "disease", target_column="disease_reference", target_type="reference"
    )

    # print the final dataframe to show below
    print(df.to_markdown(tablefmt="rst", index=False))

Here's what it looks like in the end:

======= ======= ============== ============== =========== ======================================================= ============= ======================================================
species strain  organ          disease        organ_curie organ_reference                                         disease_curie disease_reference
======= ======= ============== ============== =========== ======================================================= ============= ======================================================
RAT     F 344/N LUNG           ADENOCARCINOMA bto:0000763 prefix='bto' identifier='0000763' name='lung'           doid:299      prefix='doid' identifier='299' name='adenocarcinoma'
MOUSE   B6C3F1  NOSE           INFLAMMATION   bto:0000840 prefix='bto' identifier='0000840' name='nose'           symp:0000061  prefix='symp' identifier='0000061' name='inflammation'
RAT     F 344/N ADRENAL CORTEX NECROSIS       bto:0000045 prefix='bto' identifier='0000045' name='adrenal cortex' symp:0000132  prefix='symp' identifier='0000132' name='necrosis'
======= ======= ============== ============== =========== ======================================================= ============= ======================================================

Grounding using a single vocabulary
-----------------------------------

If you're looking for just grounding to just a single namespace, and not a
pre-consolidated lexicon from Biolexica, you can use :func:`pyobo.get_grounder` like:

.. warning::

    This functionality requires having the latest development version of PyOBO installed
    from https://github.com/biopragmatics/pyobo.

.. code-block:: python

    import pandas as pd
    import pyobo

    uberon_grounder = pyobo.get_grounder("uberon")

    data_url = "https://raw.githubusercontent.com/OBOAcademy/obook/master/docs/tutorial/linking_data/data.csv"
    df = pd.read_csv(data_url)
    df = df[["species", "strain", "organ"]]

    # this adds a new column `organ_curie` that has strings
    # for the Bioregistry-standardized CURIEs
    uberon_grounder.ground_pandas_df(df, "organ", target_column="organ_curie")

    # this adds a new column `organ_reference` that has reference objects
    # for Bioregistry-standardized references (e.g., pre-parsed prefix, identifier, and name)
    uberon_grounder.ground_pandas_df(
        df, "organ", target_column="organ_reference", target_type="reference"
    )

    # print the final dataframe to show below
    print(df.to_markdown(tablefmt="rst", index=False))

This returns the following:

======= ======= ============== ============== ====================================
species strain  organ          organ_curie    organ_reference
======= ======= ============== ============== ====================================
RAT     F 344/N LUNG           uberon:0002048 prefix='uberon' identifier='0002048'
                                              name='lung'
MOUSE   B6C3F1  NOSE           uberon:0000004 prefix='uberon' identifier='0000004'
                                              name='nose'
RAT     F 344/N ADRENAL CORTEX uberon:0001235 prefix='uberon' identifier='0001235'
                                              name='adrenal cortex'
======= ======= ============== ============== ====================================
