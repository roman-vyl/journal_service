## 1. Files (apply, only after the owner has reviewed this change)

- [ ] 1.1 `.github/workflows/ci.yml` as in D1.
- [ ] 1.2 `.github/workflows/docker-publish.yml` as in D3.
- [ ] 1.3 `Makefile` with `lint`, `format-check`, `typecheck`, `test`, `verify` (D2).
- [ ] 1.4 `.dockerignore` allowlist (D5).
- [ ] 1.5 `openspec validate --all --strict` passes locally for all active changes; fix documentation if it does not.
- [ ] 1.6 `make verify` passes locally; `docker build` of the image succeeds with the new `.dockerignore` (context shrinks, no `.venv`).

## 2. Verification (needs the branch merged to `main`, on the owner's word)

- [ ] 2.1 CI is green on the pull request or branch push.
- [ ] 2.2 After the merge, Docker Publish runs once and pushes `:<sha>` and `:main`.
- [ ] 2.3 The tag is a manifest list with `linux/amd64` and `linux/arm64`.
- [ ] 2.4 `docker pull ghcr.io/roman-vyl/journal_service:<sha>` works on the Mac with the credentials `Deploy Demo` uses (package access, point 4 above).
- [ ] 2.5 The pulled container starts non-root and its health check turns healthy with the documented environment.
- [ ] 2.6 The canonical `JOURNAL_IMAGE` value is recorded for the pin PR.

## 3. Out of this change

- [ ] 3.1 `JOURNAL_IMAGE` pin in `bbb_stack` `deploy/images.env` (separate PR).
- [ ] 3.2 Merge of the `journal_service` branch.
