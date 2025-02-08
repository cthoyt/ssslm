"""Command line interface for :mod:`ssslm`."""

import click

__all__ = [
    "main",
]


@click.command()
def main() -> None:
    """CLI for SSSLM."""


if __name__ == "__main__":
    main()
