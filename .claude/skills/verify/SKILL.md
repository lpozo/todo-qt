---
name: verify
description: Phase 8 of the AI-assisted coding workflow — final verification and integration gate, also the last step of the quick track. Use after /orchestrate or /quick-change, when all tasks are merged into the change's branch and you're preparing the PR. Invoked by /verify. Runs the full toolchain and cross-checks acceptance criteria.
---

# Phase 8 — Verification & Integration

Your job: prove the assembled system is correct, secure, and complete — not just that individual tasks passed.

## Inputs

- The change's branch (`git branch --show-current`), with all task commits squash-merged.
- **Full track:** `docs/workflow/<slug>/requirements.md` (acceptance criteria) and `spec.md` (behaviors).
- **Quick track:** `docs/workflow/<slug>/brief.md` instead — its acceptance criteria and regression test. Check 3 applies only here.

## Sync with the default branch first

The checks must run on the code that will be merged:

```bash
git fetch origin
git rebase origin/<base>          # <base>: the default branch
```

If the rebase conflicts, resolve only the conflicts — don't change behavior — and halt to ask the user if a conflict touches logic you don't understand. Without a remote, skip this step.

## Checks (run in order; halt on first hard failure)

These are CI's jobs (see `/env-ci-setup`), run locally the same way, so a pass here predicts a green CI. Run tools through `uv run`: they live in the project's `.venv`.

### 1. Static analysis

```bash
uv run pre-commit run --all-files   # ruff check, ruff format, bandit (src/), as on every commit
uv run mypy src                     # strictness comes from [tool.mypy] in pyproject.toml
uv run lint-imports                 # import-linter contracts from [tool.importlinter]
```

### 2. Test suite

```bash
uv run pytest -n auto --cov --cov-branch --cov-report=term-missing --cov-report=xml
```

- Coverage must meet `fail_under` in `[tool.coverage.report]`; pytest fails otherwise. Don't pass a different threshold on the command line.
- Run integration tests against **real services** via `testcontainers`, not mocks.
- **Optional — coverage of the change itself.** In a code base whose overall coverage sits below the threshold for reasons unrelated to this change, check the lines the change touched instead:
  ```bash
  uvx diff-cover coverage.xml --compare-branch=origin/<base> --fail-under=<threshold>
  ```
  It lists the changed lines no test executes.

### 3. Red-first evidence (quick track only)

The quick track commits the regression test alone, before the fix, as `test(<slug>): reproduce …`. Confirm that commit exists, holds no fix, and that the test really failed there:

```bash
red=$(git log --format=%H --grep="^test(<slug>): reproduce" origin/<base>..HEAD)
git diff --name-only "$red^" "$red"            # only test files and brief.md
git worktree add -q .worktrees/verify-red "$red"
uv sync --frozen -q --directory .worktrees/verify-red
uv run --frozen --directory .worktrees/verify-red -- pytest "<regression test node id>" -q; echo "pytest exit code: $?"
git worktree remove .worktrees/verify-red
```

- **No such commit,** or one that also changes source files: there's no evidence the test catches the problem. Report it; don't paper over it by rewriting history.
- **The test must fail there with exit code 1,** and the output must show the reported problem (the wrong value, the exception from the brief). Exit code 2–5 means it errored or collected nothing, which isn't a reproduction.
- On the branch's current head the same test passes; check 2 covered that.

### 4. Mutation testing (optional, high-stakes modules only)

Coverage shows which lines ran, not whether the tests would notice them being wrong. For code where a missed bug is expensive, mutate it and see which mutants the tests fail to kill:

```bash
rm -rf mutants                       # mutmut reuses cached results when only tests change
uv run --with mutmut mutmut run
uv run --with mutmut mutmut export-cicd-stats
uv run python -c "import json; s = json.load(open('mutants/mutmut-cicd-stats.json')); k = s['killed']; t = k + s['survived'] + s['no_tests']; print(f'mutation score: {k}/{t} = {k / t:.0%}')"
uv run --with mutmut mutmut results  # surviving mutants; `mutmut show <name>` prints one's diff
```

- Choose what to mutate with `source_paths` in `[tool.mutmut]`, e.g. `source_paths = ["src/<package>/domain.py"]` — files or folders. Without it, mutmut mutates everything under `src/`, which can be slow.
- `mutants/` is mutmut's working folder; make sure `.gitignore` covers it.
- A score below 80% means the tests have gaps: for each surviving mutant, add the test that kills it, or explain why the mutant is equivalent to the original.

### 5. Security

```bash
tmpdir="$(mktemp -d)"
uv export --frozen --all-groups --no-emit-project --format requirements-txt -o "$tmpdir/requirements-audit.txt"
uvx pip-audit --strict --disable-pip --require-hashes -r "$tmpdir/requirements-audit.txt"
```

- `pip-audit` audits the exported lockfile — exactly what gets installed. (Auditing the venv with `--strict` fails on the project itself, which isn't on PyPI.)
- `bandit` already ran in step 1, through pre-commit.
- **Secrets in the branch's commits:** if `gitleaks` is installed, run `gitleaks git --redact --verbose --log-opts="origin/<base>..HEAD"` — it catches secrets committed and later removed, which a scan of the working tree misses. Otherwise, the CI Security job runs this scan on the PR.

### 6. Manual golden-path walkthrough

Automated tests verify code correctness, not feature correctness.

- For UI/CLI: invoke the feature manually, walk through the happy path and 1–2 error paths.
- For API: hit each endpoint with realistic payloads.
- Compare actual behavior to the spec's behavioral examples table.

### 7. Cross-check acceptance criteria

Open `requirements.md` and check each Must/Should item (quick track: every criterion in `brief.md`):

| Criterion | Status | Evidence |
|---|---|---|
| Given X, When Y, Then Z | ✅ | `tests/<feature>/test_foo.py::test_z` passes |

If any Must is unchecked, halt — the feature is not done.

### 8. Independent reviewer

**Spawn a fresh reviewer subagent with no prior context.** Pass only:
- The diff (`git diff origin/<base>...HEAD`).
- The spec (quick track: the brief).

Treat the reviewer's verdict as authoritative.

### 9. Changelog

Add the change to the *Unreleased* section of `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/) format, under *Added*, *Changed*, *Fixed*, …), written for users rather than as a commit list. Create the file with that section if it doesn't exist. The release PR later moves *Unreleased* under the new version (see the release process from `/env-ci-setup`). Commit it: `docs(<slug>): add changelog entry`.

### 10. Publish

Push the rebased branch — `--force-with-lease` refuses if someone else pushed in the meantime:

```bash
git push --force-with-lease
```

If `/req-research` opened a draft PR (`gh pr view --json number,isDraft,title`), replace its body with the summary below (`gh pr edit --body-file -`), make sure its title still describes the whole change as a Conventional Commit (it becomes the squash commit), and mark it ready: `gh pr ready`. Otherwise create it:

```bash
gh pr create --title "<type>(<slug>): <one-line summary>" --body "$(cat <<'EOF'
## Summary
- ...

## Acceptance Criteria
- [x] ...

## Verification
- ruff/mypy clean
- pytest <N> passed, coverage <X>%
- bandit/pip-audit/gitleaks clean
- Manual walkthrough completed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Best practices

- **Same checks as CI.** Every command here is one of CI's jobs; don't substitute different flags or thresholds locally.
- **Pin transitive deps.** `uv.lock` is the source of truth; CI's `uv sync --locked` fails if it's stale.
- **AI reviewers complement, not replace.** CodeRabbit / Greptile catch different things than humans — use both.

## Exit criteria

- Checks 1, 2, and 5–10 are green; check 3 too on the quick track, and check 4 where mutation testing was warranted.
- Every Must acceptance criterion has explicit test evidence.
- Reviewer signed off.
- PR is open and CI is green.

## After verification

Report the verification table to the user. Hand off the PR URL.
