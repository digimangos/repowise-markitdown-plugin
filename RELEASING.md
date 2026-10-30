# Releases and build artifacts

## Version policy

`project.version` in `pyproject.toml` is the single authoritative version. Use
`MAJOR.MINOR.PATCH`, without leading zeroes, prerelease identifiers or build metadata.
Bump PATCH for compatible fixes, MINOR for compatible features and MAJOR for breaking
changes. While the project is at 0.x, minor versions may introduce breaking changes.
Run `uv lock` after changing the version so the locked local package stays consistent.

Release tags must be exactly `v` followed by that version, for example `v2.0.0`.
The validation helper checks both archive filenames and their embedded package
metadata against `pyproject.toml`. No second runtime version constant is maintained.

## CI builds

Every push and pull request runs the required Python 3.11, 3.13 and 3.14 test,
Ruff lint and format checks, then builds a wheel and source distribution. Each matrix
job uploads `distributions-python-<version>` containing both packages and `SHA256SUMS`,
retained for 14 days. These are development snapshots with the declared package
version, not releases. Identify them by workflow run and commit, not version alone.

Python 3.11 covers the declared minimum supported version; 3.13 remains the
release-build baseline and 3.14 covers the newest supported interpreter. Python
3.12 remains within the declared support range but has no separate CI job.
Python 3.15 coverage is deferred until the full dependency stack supports it:
the locked `onnxruntime==1.31.0`, required through `markitdown[all]`, has neither a
CPython 3.15 wheel nor a source distribution. Do not remove MarkItDown extras to
make that job pass. Recheck dependency availability before adding 3.15 to the
required matrix.

Authenticate with access to this private repository, then download a successful
run's artifact. Select the run and inspect its commit before installing its code:

```sh
gh run list --repo digimangos/repowise-markitdown-plugin --workflow tests.yml
RUN_ID=123456789 # Replace with the reviewed successful run.
gh run download "$RUN_ID" \
  --repo digimangos/repowise-markitdown-plugin \
  --name distributions-python-3.13 --dir downloaded-build
cd downloaded-build
shasum -a 256 -c SHA256SUMS
```

GitHub's artifact download wraps these files in a ZIP when downloaded through the
web interface. Extract that ZIP before checking the checksums.

## Maintainer release procedure

1. Review the version change and `uv.lock`, merge the release-ready code, and ensure
   CI passes on the intended commit. Normally use `main` after the implementation
   and release automation have merged. Do not release an unreviewed feature branch.
2. A maintainer creates and pushes the matching `vMAJOR.MINOR.PATCH` tag at that
   commit. Tags are intentional release requests. Never move or reuse a release tag.
3. The Release workflow validates the tag before installing dependencies, reruns the
   full matrix, then downloads the Python 3.13 build. It validates the package
   metadata again, creates a draft with GitHub-generated release notes, uploads the
   wheel, sdist and `SHA256SUMS`, and publishes only after every upload succeeds.

Only the publishing job has `contents: write`; all other jobs have read-only
repository access. Concurrent release runs for the same tag are serialised without
cancelling an in-flight publication. Test jobs also queue rather than cancel each
other. There is no PyPI publishing, registry credential or additional secret.

On failure, rerun the failed workflow jobs from the tagged commit. An interrupted
draft is resumed only when its stored `target_commitish` matches the originating
workflow commit SHA, set explicitly at creation. A missing SHA, branch name or
different SHA is rejected, including when a later workflow follows a moved tag.
Existing assets must match byte-for-byte and only missing assets
are uploaded. A complete published release is a no-op after asset verification.
Different assets, unexpected assets, an incomplete published release or a moved
remote tag fail closed for maintainer review. No asset is overwritten and release
notes are not regenerated on reruns. Do not delete assets to force a rerun through;
investigate the mismatch and make a new version if necessary.

Building this automation does not itself create a tag or release.

## Install a release

Releases in a private repository require repository access. There is no
PyPI publishing step. Use `gh` authentication to download the packages
rather than embedding tokens in installation URLs:

```sh
VERSION=2.0.0 # Example only; choose an existing reviewed release.
gh release download "v$VERSION" \
  --repo digimangos/repowise-markitdown-plugin \
  --pattern '*.whl' --pattern '*.tar.gz' --pattern SHA256SUMS \
  --dir "release-$VERSION"
cd "release-$VERSION"
shasum -a 256 -c SHA256SUMS
```

For an existing Repowise virtual environment, activate it and install the wheel:

```sh
python -m pip install ./repowise_markitdown-*.whl
repowise plugins
```

Version 2 integrates with Repowise's document-extractor seam. Use a Repowise
version that provides that seam; installing the wheel cannot add it to an older
host. See [README](README.md#requirements) for requirements and migration guidance.

Alternatively, for a uv-managed Repowise tool installation:

```sh
uv tool install --force --python 3.13 \
  --with "$(pwd)/repowise_markitdown-$VERSION-py3-none-any.whl" \
  repowise
```

Development and CI use a compatible Repowise revision pinned through
`tool.uv.sources` and `uv.lock`. Source overrides are not embedded in wheel
dependency metadata. Check `repowise plugins` before indexing.
This command replaces that uv tool environment; do not run it merely to inspect a
download. CI wheels can be installed the same way after checking their checksums.
Use the `.tar.gz` file with pip instead if a source installation is needed.
All approaches install the plugin into Repowise's environment and retain the
`markitdown[all]` dependency. Checksums detect file corruption, not publisher identity;
download only from a trusted run or release in this repository.

## Local release checks

Start with an empty `dist` directory for a new build. The validator deliberately
rejects stale distributions and checksums left over from a different build.

```sh
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
uv run python scripts/validate_release.py --dist dist
uv run python scripts/validate_release.py --tag v2.0.0 --dist dist
```

Replace the example tag with the current declared version. Invalid tags and
distribution mismatches exit non-zero. Publication tests use a mocked GitHub CLI;
local checks do not need release permissions or create GitHub resources.
