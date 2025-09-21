[doc("run tests")]
test:
    just _cov erase
    uvx --from coverage[toml] coverage erase
    uv run --isolated --group tests --extra rdflib --extra web --extra gilda-slim --extra pandas --extra gliner --extra ontology -m coverage run -p -m pytest
    # uv run --isolated --group tests --extra scispacy --group en-core-sci-sm -m coverage run -p -m pytest
    just _cov combine
    just _cov report
    just _cov html

_cov command:
    uvx --from coverage[toml] coverage {{command}}
