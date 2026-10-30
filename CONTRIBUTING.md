# Contributing

Bug reports, documentation improvements and focused pull requests are welcome.
Participation is covered by our [code of conduct](CODE_OF_CONDUCT.md).

## Before starting

Search [existing issues](https://github.com/digimangos/repowise-markitdown-plugin/issues)
and open an issue before making a substantial behavioural change. Report security
vulnerabilities privately using [SECURITY.md](SECURITY.md), not a public issue.

## Local setup

Use Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/digimangos/repowise-markitdown-plugin.git
cd repowise-markitdown-plugin
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The lockfile pins a compatible Repowise revision. Do not remove the MarkItDown
extras or weaken host limits to make tests pass. See [RELEASING.md](RELEASING.md)
for build and distribution checks.

## Pull requests

Create a branch from `main`, keep changes focused and explain the problem and
user-visible impact. Add focused regression tests for changed behaviour and run
the commands above. Update the README when installation, supported formats,
processing stages or limitations change. Never include credentials or confidential
documents; use small synthetic PDFs for reproducible examples.

PDF extraction must use the supplied byte snapshot, retain the original source
path and avoid repository-side Markdown copies. Repowise owns discovery, worker
execution, limits and caching. Keep those responsibilities in the host.

Contributions are made under the repository's [ISC licence](LICENSE).
