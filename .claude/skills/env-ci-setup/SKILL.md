---
name: env-ci-setup
description: Configure GitHub Actions CI for a workflow-baseline Python project. Creates .github/workflows/ci.yml (pre-commit hooks, mypy, import-linter, pytest with a coverage threshold across supported Pythons, pip-audit, gitleaks), a PR-title check, Dependabot config, squash-only merge rules for the default branch, and optionally a tag-driven release.yml. Idempotent — backs up existing workflows before overwriting.
---

# env-ci-setup — GitHub Actions for the workflow baseline

Your job: stand up CI that runs the same checks as the local pre-commit hooks, plus the security and integration gates from Phase 8 (`/verify`).

## Pre-flight

1. Confirm working directory.
2. Detect existing `.github/workflows/`. If `ci.yml` exists, **back it up** to `ci.yml.bak.<timestamp>` before overwriting and tell the user.
3. Confirm the baseline from `/env-bootstrap` is in place: `uv.lock` committed, `.pre-commit-config.yaml` present, and `fail_under` set in `[tool.coverage.report]`.
4. Detect dependencies that change behavior:
   - Postgres / Redis / Kafka in `pyproject.toml` → suggest `services:` blocks for integration tests.
   - `testcontainers` → make sure Docker is available in the CI image.

## Steps

### 1. `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --locked
      - uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: ~/.cache/pre-commit
          key: pre-commit-${{ hashFiles('.pre-commit-config.yaml') }}
      # The same commit-stage hooks developers run locally: ruff, ruff format, bandit.
      - run: uv run pre-commit run --all-files --show-diff-on-failure

  types:
    name: Types
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run mypy src

  architecture:
    name: Architecture
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run lint-imports

  test:
    name: Tests (Python ${{ matrix.python }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13", "3.14"] # requires-python's minimum through the newest stable
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
          python-version: ${{ matrix.python }}
      - run: uv sync --locked
      # Fails below [tool.coverage.report] fail_under.
      - run: uv run pytest -n auto --cov --cov-branch --cov-report=term-missing

  security:
    name: Security
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0 # The secret scan needs the commits being pushed
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - name: Audit locked dependencies
        run: |
          uv export --frozen --all-groups --no-emit-project --format requirements-txt \
            -o "$RUNNER_TEMP/requirements-audit.txt"
          uvx pip-audit --strict --disable-pip --require-hashes -r "$RUNNER_TEMP/requirements-audit.txt"
      - name: Scan new commits for secrets
        env:
          GITLEAKS_VERSION: "8.30.1"
          EVENT: ${{ github.event_name }}
          BASE_REF: ${{ github.base_ref }}
          BEFORE: ${{ github.event.before }}
          AFTER: ${{ github.sha }}
        run: |
          asset="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
          base_url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
          cd "$RUNNER_TEMP"
          curl -sSfLO "$base_url/$asset"
          curl -sSfLO "$base_url/gitleaks_${GITLEAKS_VERSION}_checksums.txt"
          grep " $asset\$" "gitleaks_${GITLEAKS_VERSION}_checksums.txt" | sha256sum -c -
          tar -xzf "$asset" gitleaks
          cd "$GITHUB_WORKSPACE"
          if [ "$EVENT" = pull_request ]; then
            range="origin/$BASE_REF..HEAD"
          elif git cat-file -e "$BEFORE^{commit}" 2>/dev/null; then
            range="$BEFORE..$AFTER"
          else
            range="$AFTER" # New branch or rewritten history: scan everything reachable
          fi
          "$RUNNER_TEMP/gitleaks" git --redact --verbose --no-banner --log-opts="$range"
```

Adjust before writing:

- **Default branch:** replace `main` in `on.push.branches` if the repo's default branch differs.
- **Python matrix**, by project type (see `/env-bootstrap`): libraries and CLIs test from the minimum in `requires-python` through the newest stable CPython (`uv python list --only-downloads` shows what's available); applications test the Python they're deployed on; scripts & data projects test one Python. Don't list versions the project doesn't support.
- **Architecture job:** keep it only for the layered or hexagonal style (ADR-0001), which configures import-linter. For simple modules, delete the job and leave it out of the required checks in step 4.
- **Container scan:** if the project has a `Dockerfile`, add the `container` job below and list it in the required checks.
- **Changed-lines coverage:** if `/env-bootstrap` adopted an existing project with a coverage baseline below 85%, add the `changed-lines-coverage` job below and list it in the required checks.
- **Action pins:** actions are pinned to full commit SHAs, with the version in a comment, so a moved tag can't change what runs. The SHAs above were current when this skill was written; refresh them before writing — for each action, take the newest `vX.Y.Z` tag and its commit:
  ```bash
  git ls-remote --tags --sort=-v:refname https://github.com/actions/checkout 'v*'   # newest tag
  git ls-remote https://github.com/actions/checkout 'refs/tags/<tag>^{}'           # its commit SHA
  ```
  Dependabot (step 2) keeps them current afterward.
- **gitleaks version:** the newest release from <https://github.com/gitleaks/gitleaks/releases>. Keep the downloaded file's original name — the checksum file refers to it.

Optional `changed-lines-coverage` job, for adopted projects whose `fail_under` is an adoption baseline below 85% — it holds each PR's new and changed lines to 85%, so total coverage can only rise:

```yaml
  changed-lines-coverage:
    name: Changed-lines coverage
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0 # diff-cover compares with the base branch
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          enable-cache: true
      - run: uv sync --locked
      - run: uv run pytest -n auto --cov --cov-branch --cov-report=xml
      - env:
          BASE_REF: ${{ github.base_ref }}
        run: uvx diff-cover coverage.xml --compare-branch="origin/$BASE_REF" --fail-under=85
```

Optional `container` job, for projects with a `Dockerfile` — builds the image and fails on known high or critical vulnerabilities in it:

```yaml
  container:
    name: Container
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - run: docker build -t app:ci .
      - name: Scan the image
        env:
          TRIVY_VERSION: "0.75.0"
        run: |
          asset="trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
          base_url="https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}"
          cd "$RUNNER_TEMP"
          curl -sSfLO "$base_url/$asset"
          curl -sSfLO "$base_url/trivy_${TRIVY_VERSION}_checksums.txt"
          grep " $asset\$" "trivy_${TRIVY_VERSION}_checksums.txt" | sha256sum -c -
          tar -xzf "$asset" trivy
          "$RUNNER_TEMP/trivy" image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed app:ci
```

Why these choices:

- **`uv sync --locked`** fails when `uv.lock` is out of date with `pyproject.toml`, instead of silently re-resolving.
- **Pre-commit in the lint job** runs exactly the hooks developers run on commit, at the `uv.lock` versions — one definition, no drift. (The pre-commit gitleaks hook only scans staged changes, so CI scans commits separately.)
- **The secret scan covers the commits in the PR or push**, so a secret added and removed again within a PR is still caught. It uses the gitleaks binary directly: `gitleaks-action` needs a license key for organization-owned repos.
- **`pip-audit` audits the exported lockfile**, which is exactly what gets installed. Auditing the virtualenv with `--strict` fails on the project itself, which isn't on PyPI.
- **Coverage is enforced by `fail_under`**, so the threshold lives in `pyproject.toml` and applies the same way locally, in CI, and in `/verify`. Uploading to Codecov is optional; if you add it, don't make it fail the build.

### 2. `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: uv
    directory: /
    schedule:
      interval: weekly
```

Dependabot updates the pinned action SHAs (and their version comments) and the locked dependencies, through PRs that CI checks like any other.

### 3. `.github/workflows/pr-title.yml`

PRs are squash-merged (step 4), so a PR's title becomes the commit on the default branch. Check it's a Conventional Commit:

```yaml
name: PR title

on:
  pull_request:
    types: [opened, edited, reopened, synchronize]

permissions:
  contents: read

jobs:
  pr-title:
    name: PR title
    runs-on: ubuntu-latest
    steps:
      - name: Check the title is a Conventional Commit
        env:
          TITLE: ${{ github.event.pull_request.title }} # Via env, never inlined into the script
        run: |
          pattern='^(feat|fix|refactor|perf|docs|test|chore|build|ci|style|revert)(\([a-z0-9][a-z0-9._/-]*\))?!?: [^ ].*$'
          if [[ "$TITLE" =~ $pattern ]]; then
            echo "OK: $TITLE"
          else
            echo "::error::PR title must be a Conventional Commit, like 'feat(auth): add login'. Squash merges make it the commit on the default branch. Got: $TITLE"
            exit 1
          fi
```

### 4. GitHub merge rules (ask before applying)

These change the repository's settings on GitHub, so show the user the commands and run them only with their go-ahead. Ask one question first: **how many approving reviews should a PR need?** Use 1 or more for teams; 0 for a solo maintainer, who can't approve their own PRs.

**Squash merges only**, with the PR title and body as the commit, and branches deleted after merging:

```bash
gh api -X PATCH "repos/{owner}/{repo}" \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true
```

**A ruleset protecting the default branch:** changes arrive through PRs that pass CI, history stays linear, and the branch can't be force-pushed or deleted. Write this to a temporary file — it's not part of the repo — listing one required check per CI job name, including every Python in the test matrix. `integration_id` 15368 is GitHub Actions, so no other app can satisfy the checks.

```json
{
  "name": "Protect the default branch",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          {"context": "Lint", "integration_id": 15368},
          {"context": "Types", "integration_id": 15368},
          {"context": "Architecture", "integration_id": 15368},
          {"context": "Tests (Python 3.12)", "integration_id": 15368},
          {"context": "Tests (Python 3.13)", "integration_id": 15368},
          {"context": "Tests (Python 3.14)", "integration_id": 15368},
          {"context": "Security", "integration_id": 15368},
          {"context": "PR title", "integration_id": 15368}
        ]
      }
    }
  ]
}
```

```bash
gh api -X POST "repos/{owner}/{repo}/rulesets" --input "$ruleset_file"
```

Rulesets on private repositories need a paid GitHub plan. If the API refuses with 403 or 404 there, fall back to classic branch protection with the same intent:

```bash
gh api -X PUT "repos/{owner}/{repo}/branches/<default-branch>/protection" --input - <<'EOF'
{
  "required_status_checks": {"strict": true, "contexts": ["Lint", "Types", "Architecture", "Tests (Python 3.12)", "Tests (Python 3.13)", "Tests (Python 3.14)", "Security", "PR title"]},
  "enforce_admins": true,
  "required_pull_request_reviews": {"required_approving_review_count": 1, "dismiss_stale_reviews": true},
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```

### 5. (Optional) `.github/workflows/release.yml`

Whether to add it follows the project type (see `/env-bootstrap`): libraries need it, with the PyPI job; CLIs usually, with the PyPI job if they're published; applications only for GitHub releases (delete the PyPI job); scripts & data projects don't. Confirm with the user. Releases are **tag-driven**: nothing in CI pushes to the protected default branch.

```yaml
name: Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: read

jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0 # To check the tag is on the default branch
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - name: Check the tag
        env:
          DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
        run: |
          version="$(uv version --short)"
          if [ "v$version" != "$GITHUB_REF_NAME" ]; then
            echo "::error::Tag $GITHUB_REF_NAME doesn't match the project version $version."
            exit 1
          fi
          if ! git merge-base --is-ancestor "$GITHUB_SHA" "origin/$DEFAULT_BRANCH"; then
            echo "::error::Tag $GITHUB_REF_NAME isn't on $DEFAULT_BRANCH. Release only merged, CI-checked commits."
            exit 1
          fi
      - run: uv build
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with:
          name: dist
          path: dist/

  github-release:
    name: GitHub release
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: dist
          path: dist/
      - env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" dist/* --repo "$GITHUB_REPOSITORY" --generate-notes --verify-tag

  # Libraries only: delete this job if the project isn't published to PyPI.
  pypi:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write # Trusted publishing: PyPI trusts this workflow; no stored token
    steps:
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: dist
          path: dist/
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
      - run: uv publish
```

For PyPI publishing, the user sets up trusted publishing once: on pypi.org, add a GitHub publisher for the project (owner, repository, workflow `release.yml`, environment `pypi`), and create a `pypi` environment in the repository's settings — optionally requiring a reviewer, so every publish needs a human click.

Explain the release process to the user (and add it to the project's `CONTRIBUTING.md` or README if it has one):

1. **Release PR.** On a `chore/release-<version>` branch, bump the version — `uv version --bump patch|minor|major`, chosen from the Conventional Commits since the last tag: any breaking change (`!` or `BREAKING CHANGE:`) → major, any `feat` → minor, otherwise patch — and move the changelog's *Unreleased* entries under the new version. Title: `chore(release): <version>`.
2. **Tag the merged commit:**
   ```bash
   git switch <default-branch> && git pull
   git tag -a v<version> -m "v<version>"
   git push origin v<version>
   ```
3. **The workflow** checks the tag matches the version and is on the default branch, builds, creates the GitHub release with generated notes, and publishes to PyPI.

Why tag-driven: tools that commit the version bump and tag from CI (like python-semantic-release) need to push to the default branch, which the merge rules forbid. Release-please opens its own release PRs instead, but PRs opened with the default `GITHUB_TOKEN` don't trigger CI, so its PRs can't pass the required checks without a GitHub App or personal token.

### 6. Smoke

Validate the workflow files before committing:

```bash
uvx --from actionlint-py actionlint
```

Then run each job's commands locally (`uv sync --locked`, `uv run pre-commit run --all-files`, `uv run mypy src`, `uv run lint-imports`, the pytest command, the audit commands) — they should all pass before CI does.

## Operating principles

- **One definition per check.** Lint runs the pre-commit hooks; tools come from `uv.lock`; coverage comes from `pyproject.toml`. Don't restate a check in CI with different flags.
- **Least privilege.** `permissions: contents: read` at the top; grant more only to the job that needs it.
- **Pin what runs.** Actions by commit SHA, downloaded binaries by checksum.
- **Matrix only across supported Pythons.** Tests run on every supported version; other jobs on one.
- **Concurrency cancellation.** Old runs cancel on new pushes — saves CI minutes and surfaces the latest result.

## Exit criteria

- `.github/workflows/ci.yml`, `.github/workflows/pr-title.yml`, and `.github/dependabot.yml` exist, and `actionlint` reports nothing.
- The merge rules are applied, or the user chose not to and has the commands.
- If the project publishes releases: `release.yml` exists and the user knows the release process and the one-time PyPI setup.
- Each job's commands run successfully locally.
- A summary of files created/modified, with backup paths if any.

## After completion

Suggest: push the workflows to a branch, open a PR, and verify the checks run on GitHub — required checks must have run at least once before GitHub lists them. Then apply the merge rules from step 4 if the user agreed. After that, run `/env-doctor` to confirm the full baseline is green, then `/req-research` to start the first feature.
