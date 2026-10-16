## ADDED Requirements

### Requirement: CI verifies every change

The repository SHALL run a CI workflow on every pull request and on every push to `main`
that checks lint, formatting, types, tests, OpenSpec strict validation and that the Docker
image builds.

#### Scenario: Pull request
- **WHEN** a pull request is opened or updated
- **THEN** CI runs `make verify`, strict OpenSpec validation and a Docker build without pushing

#### Scenario: A check fails
- **WHEN** any CI check fails on `main`
- **THEN** no image is published for that commit

### Requirement: Images are published only for green commits on main

The repository SHALL publish an image to GHCR only after the CI workflow succeeded on
`main`, built from the commit that CI ran on, using only `contents: read` and
`packages: write` permissions.

#### Scenario: Green main
- **WHEN** CI completes successfully on a push to `main`
- **THEN** the publish workflow builds that exact commit and pushes it

#### Scenario: Other branches
- **WHEN** CI runs for a pull request or a branch other than `main`
- **THEN** nothing is pushed to the registry

### Requirement: Image reference contract

Published images SHALL be named `ghcr.io/<owner>/journal_service`, tagged with the full
40-character commit SHA and with `main`, and SHALL be multi-architecture manifest lists
for `linux/amd64` and `linux/arm64`. Deployments SHALL pin the SHA tag only.

#### Scenario: Tags
- **WHEN** an image is published for commit `S`
- **THEN** tags `S` (40 hex characters) and `main` exist and no `latest` tag is created

#### Scenario: Pin format
- **WHEN** `bbb_stack` pins the image
- **THEN** `JOURNAL_IMAGE` is `ghcr.io/<owner>/journal_service:<40-hex SHA>`

### Requirement: Docker build context is minimal

The repository SHALL provide a `.dockerignore` that sends only `pyproject.toml`,
`README.md` and `src` to the Docker build.

#### Scenario: Local build
- **WHEN** the image is built from a working copy that contains `.venv`, `.git` and caches
- **THEN** none of them are in the build context
