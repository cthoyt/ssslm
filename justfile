test:
    uvx --from coverage[toml] coverage erase
    uv run --isolated --group tests --extra rdflib --extra web --extra gilda-slim --extra pandas --extra gliner -m coverage run -p -m pytest
    # uv run --isolated --group tests --extra scispacy --group en-core-sci-sm -m coverage run -p -m pytest
    uvx --from coverage[toml] coverage combine
    uvx --from coverage[toml] coverage report
    uvx --from coverage[toml] coverage html
