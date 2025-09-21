[doc("run unit and integration tests")]
test:
    just coverage erase
    uv run --group tests --all-extras --no-extra scispacy --no-extra gilda -m coverage run -p -m pytest
    # skip scispacy tests for now
    just coverage combine
    just coverage report
    just coverage html

[doc("run `coverage` with a given subcommand")]
@coverage command:
    uvx --from coverage[toml] coverage {{command}}
