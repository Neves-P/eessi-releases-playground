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

- `eessi-create-revision`
- `eessi-cvmfs-provenance`
- `eessi-github-release`
- `eessi-zenodo-lookup`
- `eessi-create-cff`

Generate and validate a citation file from Zenodo metadata with:

```bash
eessi-create-cff --input metadata/.zenodo.json --output CITATION.cff
```

Without arguments, `eessi-create-cff` reads `.zenodo.json` and writes
`CITATION.cff` in `GITHUB_WORKSPACE`, or in the current directory when that
environment variable is not set.

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

## Coordinated revision manifests

Resolve component releases, combine them with reviewed CVMFS provenance, and
write a strictly validated manifest with:

```bash
eessi-create-revision \
    --revision eessi-2026.09-poc.1 \
    --component \
        software_layer Neves-P/software-layer eessi-2026.09-poc.1 \
    --cvmfs-provenance \
        provenance/cvmfs/software.eessi.io/software.eessi.io-rev0006.json \
    --cvmfs-repository software.eessi.io \
    --cvmfs-snapshot software.eessi.io-rev0006 \
    --output revisions/eessi-2026.09-poc.1.json
```

The command queries Zenodo Sandbox by default. Pass `--zenodo-production` to
query production Zenodo. It only reads the supplied CVMFS JSON and never
invokes `cvmfs_server`.

The generated manifest is schema-versioned, deterministic JSON. Components are
serialized in role order, and the complete canonical CVMFS provenance document
is embedded in the manifest. The command strictly reloads the generated file,
rejecting malformed data rather than coercing it. The current PoC requires the
software-layer component and permits additional supported component roles.

The manifest contains the version and Concept DOIs of each component. It does
not contain its own top-level EESSI revision DOI, because Zenodo only creates
that DOI after archiving the GitHub Release that contains the manifest.
