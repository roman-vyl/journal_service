## Context

Compared on 2026-10-16: `.github/workflows` of `strategy_runtime`, `strategy_engine` and
`research_service`. The three publish workflows are byte-for-byte the same; the CI
workflows differ only in their verification steps.

## Conventions kept (from the existing services)

| Aspect | Existing convention | Used here |
| --- | --- | --- |
| CI triggers | `pull_request`, `push` to `main` | same |
| Publish trigger | `workflow_run` of workflow "CI", branch `main`, type `completed`, job `if` conclusion is `success` | same |
| Source of the built commit | checkout `ref: workflow_run.head_sha` | same |
| Permissions | `contents: read`, `packages: write` (workflow level) | same, nothing wider |
| Registry login | `docker/login-action@v3`, `ghcr.io`, `github.actor`, `GITHUB_TOKEN` | same |
| Image name | `ghcr.io/${{ github.repository }}` (underscored repo name) | `ghcr.io/roman-vyl/journal_service` |
| Tags | full commit SHA and `main` | same; no `latest`, no short SHA |
| Platforms | `linux/amd64,linux/arm64` with QEMU and Buildx (Runtime #18, "native images on arm64 hosts") | same |
| Runner | `ubuntu-latest` | same |
| Python | `actions/setup-python@v5`, 3.12; `pip install '.[dev]'` then `rm -rf src/*.egg-info` (Engine, Research) | same |
| Verify entry point | `make verify` | same, see D2 |

## Decisions

### D1. CI steps

On pull requests and on pushes to `main`: checkout, Python 3.12, install, `make verify`
(ruff check, ruff format check, mypy, pytest), OpenSpec strict validation, and a Docker
build of the image (not pushed).

- OpenSpec validation: `npm install -g @fission-ai/openspec@1.7.0` then
  `openspec validate --all --strict`, as in `research_service` (the repository has no
  `package.json` and gets none). This validates every active change, so the changes now on
  the branch must pass strict validation; any fix is a documentation edit made in apply.
- Docker build in CI, as in `research_service` (Runtime and Engine do not have it). The
  publish job runs only after merge, so a broken Dockerfile would otherwise be found after
  `main` is already updated.

### D2. Makefile

`journal_service` has no Makefile; all other services expose `make verify`. A minimal
Makefile with `lint`, `format-check`, `typecheck`, `test` and `verify` is added, calling
`python -m ruff`, `python -m mypy` and `python -m pytest` on an already installed
environment (the Research/Engine style, no venv management). It adds no application code.

### D3. Publish workflow

The same as the three existing services, with the image name taken from
`github.repository`. It runs only for a successful CI run on `main` and builds the exact
commit CI ran on.

### D4. Image contract (what `bbb_stack` pins)

- Reference: `ghcr.io/roman-vyl/journal_service:<sha>` where `<sha>` is the 40-hex commit
  SHA on `main` whose CI succeeded. Canonical pin:
  `JOURNAL_IMAGE=ghcr.io/roman-vyl/journal_service:<40-hex SHA>` in `deploy/images.env`.
- `:main` is a moving convenience tag and is never pinned. No `latest`.
- The tag is a multi-arch manifest list (`linux/amd64`, `linux/arm64`).
- Inside the image: non-root user `journal-service`, entrypoint `journal-service`, port
  8097 (`JOURNAL_PORT`), `HEALTHCHECK` on `GET /health`; required environment
  `JOURNAL_RUNTIME_SOURCE_PATH` and `JOURNAL_DB_PATH`. Mounts and ports on the host are
  `bbb_stack` concerns.

### D5. `.dockerignore`

Allowlist as in `research_service`: ignore everything, then allow `pyproject.toml`,
`README.md` and `src`. This matches the `COPY` lines of the Dockerfile exactly.

## Points for the owner to confirm

1. Makefile (D2) versus calling the tools directly in the workflow. Recommended: Makefile,
   same as every other service.
2. Docker build step in CI (D1). Recommended: yes.
3. OpenSpec validation through a global npm install pinned to 1.7.0 (Research) versus a
   `package.json` with a dev dependency (Runtime, 1.6.0). Recommended: the global install.
4. Package visibility. `journal_service` was created private. `Deploy Demo` in `bbb_stack`
   pulls with its own `GITHUB_TOKEN` (`packages: read`), which can read a package of another
   repository only if that package is public or grants access to `bbb_stack`. The other
   services' repositories are public. Confirm whether `journal_service` stays private and
   the package access is granted, or the repository and package become public. This is a
   GitHub setting for the owner; nothing in this change changes it.

## Risks

- `workflow_run` workflows run from the default branch: the publish workflow does nothing
  until it exists on `main`, and the first image appears only after this branch is merged
  (on the owner's word).
- QEMU arm64 builds are slower than native ones; the image is pure Python without
  dependencies, so the cost is small.
