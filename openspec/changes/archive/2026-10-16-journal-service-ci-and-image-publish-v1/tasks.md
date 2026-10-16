## 1. Files (apply, only after the owner has reviewed this change)

- [x] 1.1 `.github/workflows/ci.yml` as in D1.
- [x] 1.2 `.github/workflows/docker-publish.yml` as in D3.
- [x] 1.3 `Makefile` with `lint`, `format-check`, `typecheck`, `test`, `verify` (D2).
- [x] 1.4 `.dockerignore` allowlist (D5).
- [x] 1.5 `openspec validate --all --strict` passes locally for all active changes; fix documentation if it does not.
- [x] 1.6 `make verify` passes locally; `docker build` of the image succeeds with the new `.dockerignore` (context shrinks, no `.venv`).

## 2. Verification (needs the branch merged to `main`, on the owner's word)

- [x] 2.1 CI is green on the pull request or branch push.
- [x] 2.2 After the merge, Docker Publish ran once via `workflow_run` on `42c51e2` and its build-and-push step succeeded.
- [x] 2.6 The canonical value is `JOURNAL_IMAGE=ghcr.io/roman-vyl/journal_service:42c51e2ba46acf96f1b6a1b21563377e9380e9ed`.

## 3. Out of this change

- [x] 3.1 `JOURNAL_IMAGE` pin written in `bbb_stack` `deploy/images.env`; its pull request is a separate step.
- [x] 3.2 Merge of the `journal_service` branch (#1).
