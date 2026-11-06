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

- `eessi-cvmfs-provenance`
- `eessi-github-release`
- `eessi-zenodo-lookup`
- `eessi-create-cff`

## Manual CVMFS provenance handoff

An authorized operator first captures the machine-readable output on the
Stratum 0:

```bash
sudo cvmfs_server tag \
    -i software.eessi.io-rev0006 \
    -x software.eessi.io \
    > cvmfs-tag-output.txt
```

The captured file can then be converted on an unprivileged machine:

```bash
eessi-cvmfs-provenance \
    --repository software.eessi.io \
    --snapshot software.eessi.io-rev0006 \
    --input cvmfs-tag-output.txt \
    --output provenance/cvmfs/software.eessi.io/software.eessi.io-rev0006.json \
    --cvmfs-version 2.14.1
```

The conversion command parses captured output; it never invokes
`cvmfs_server` or accesses the Stratum 0.
