## Why

`journal_service` has no CI and no image publication. `bbb_stack` already wires
`journal-service` (change `bbb-journal-service-wiring-v1`) and its deploy override needs a
`JOURNAL_IMAGE` pin, which cannot exist until a published image does. The publication
contract (name, tag policy, platforms) is what the canonical pin will depend on, so it is
fixed here before any workflow is written.

## What Changes

Copying the conventions of `strategy_runtime`, `strategy_engine` and `research_service`
(compared workflow by workflow, see design), without changing application code:

- `.github/workflows/ci.yml`: checks on pull requests and on pushes to `main`.
- `.github/workflows/docker-publish.yml`: after CI succeeds on `main`, build and push the
  image to GHCR, tagged with the full commit SHA and `main`.
- `Makefile` with the `verify` target every other service has (tooling only).
- `.dockerignore` allowlist (research_service convention), so local builds do not send
  `.venv`, `.git` and caches to Docker.

## Non-Goals

No change to application code, tests or the Dockerfile. No change to `bbb_stack`, no
`JOURNAL_IMAGE` pin (a separate PR after the first image exists), no merge of this branch,
no deployment, no registry or organization settings changed from here.

## Capabilities

### New Capabilities

- `ci-and-image-publish`: what CI verifies and what an published image looks like.

## Impact

- New files only, in `journal_service`.
- Defines the canonical value format of `JOURNAL_IMAGE` for `bbb_stack`.
