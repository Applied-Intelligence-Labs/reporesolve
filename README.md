# RepoResolve

**RepoResolve** helps you set up a shared environment across multiple research repos without trying to blindly install everything.

Instead of breaking your system, it helps you **understand, resolve, and generate a working environment first**.

## What It Does

RepoResolve focuses on the parts that are **safe and deterministic**:

- Scans repos for dependency manifests
- Detects setup clues from READMEs, scripts, Dockerfiles, and CI
- Selects relevant dependency files
- Identifies conflicts before installation
- Guides you through resolving them
- Generates usable outputs:
  - `environment.generated.yml`
  - `manual-setup.md`
  - `manual-setup.json`
- Provides a `doctor` command to validate everything

## What It Solves

- Bootstrapping a shared Python/Conda environment across multiple repos
- Catching dependency conflicts early
- Surfacing non-Python requirements such as CUDA, MuJoCo, EGL, `apt`, and environment variables
- Giving you **inspectable, editable outputs** instead of black-box installs

## What It Doesn't Do (`v0`)

RepoResolve **does not**:

- Automatically run system installs such as `apt` or `brew`
- Set up CUDA, MuJoCo, or OpenGL for you
- Fully install and run repos end-to-end from the main flow
- Parse unsupported dependency formats

This is intentional. `v0` is **generation + validation only**.

## Quickstart

Install RepoResolve:

```bash
pip install -e .
reporesolve
```

Set your API key if you are using a provider:

```bash
OPENAI_API_KEY=your-key
# or
ANTHROPIC_API_KEY=your-key
```

## Prerequisites

Make sure you have:

- Python `3.10+`
- Git available on `PATH`
- Conda available on `PATH`
  - required for `reporesolve doctor`
  - required for `reporesolve doctor --install`
- Network access
- One configured provider:
  - OpenAI: `OPENAI_API_KEY` and the `openai` SDK
  - Anthropic: `ANTHROPIC_API_KEY` and the `anthropic` SDK

If you are cloning GitHub repos, especially private repos, set up GitHub access first:

```bash
gh auth login
# or
ssh -T git@github.com
```

If cloning fails because GitHub access is not configured, RepoResolve stops and asks you to fix access first.

## Workflow

1. Input repos in the guided TUI.
2. Clone repos.
3. Scan dependency manifests and setup clues.
4. Select relevant manifests.
5. Parse supported files:
   - `requirements*.txt`
   - `environment.yml`
   - `environment.yaml`
6. Detect conflicts.
7. Review proposed changes:
   - accept
   - reject
   - edit
   - defer
8. Generate output files.

## Output

Each run creates:

```text
./artifacts/<run_id>/
```

Contents:

- `environment.generated.yml`
- `manual-setup.md`
- `manual-setup.json`
- `report.json`

## Doctor

After reviewing the generated files and completing the manual setup steps:

```bash
reporesolve doctor
```

`doctor` checks:

- artifact presence
- conda availability
- environment visibility
- manual setup requirements
- dependency solve via `conda env create --dry-run`

Optional disposable install validation:

```bash
reporesolve doctor --install
```

## Configuration

RepoResolve reads API keys from:

- `.env`
- environment variables

If no provider is configured, RepoResolve fails explicitly.

RepoResolve writes run outputs relative to the directory where you run the command:

- cloned repos: `./repos/`
- artifacts: `./artifacts/<run_id>/`

## Commands

- `reporesolve` - run the workflow
- `reporesolve start` - alias for the workflow
- `reporesolve doctor` - validate the latest generated run in the current directory
- `reporesolve doctor --install` - attempt disposable install validation
- `reporesolve version` - show the installed version
