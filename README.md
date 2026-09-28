# EESSI revisions

Tools for creating coordinated, citable EESSI revisions.

## Development setup

This project supports Python 3.9 and newer. Install it in editable mode with
the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Install the optional citation tooling when working with `CITATION.cff`:

```bash
python -m pip install -e ".[citation,dev]"
```

Run the unit tests with:

```bash
python -m unittest discover -s tests -v
```

## Commands

Installing the project provides these commands:

- `eessi-github-collector`
- `eessi-github-release`
- `eessi-zenodo-lookup`
- `eessi-create-cff`
