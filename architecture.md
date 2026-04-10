# RepoResolve Architecture

RepoResolve is a guided multi-repo environment resolver for research codebases.

In `v0.2.0`, it does two things well:

- generates a shared Python or Conda environment plan
- validates that generated plan with `doctor`

It does not try to fully automate system setup, CUDA, MuJoCo, or end-to-end repo execution from the main flow.

## Core Idea

RepoResolve splits setup into three layers:

1. Python or Conda layer
   - automated
   - output: `environment.generated.yml`
2. Host or system layer
   - detected and documented
   - examples: `apt`, `brew`, setup scripts, env vars
3. Runtime or hardware layer
   - detected and documented
   - examples: CUDA, GPU, EGL, OpenGL, MuJoCo runtime

The main architectural decision is simple: generate first, validate second.

## Main Parts

- CLI: `reporesolve/cli/main.py`
  - public commands
- TUI: `reporesolve/tui/*`
  - guided prompts and review screens
- Supervisor: `reporesolve/supervisor/*`
  - orchestrates generation and doctor flows
- Tools: `reporesolve/tools/*`
  - deterministic operations like clone, inspect, and parse
- Agent: `reporesolve/agent/*`
  - structured reasoning only
- Providers: `reporesolve/providers/*`
  - OpenAI and Anthropic adapters
- Config and storage:
  - `reporesolve/config/*`
  - `reporesolve/storage/*`

## Public Commands

- `reporesolve`
- `reporesolve start`
- `reporesolve doctor`
- `reporesolve doctor --install`
- `reporesolve version`

## Main Workflow

The main `reporesolve` command is generation-only:

```text
TUI input
-> provider validation
-> clone repos
-> inspect repos
-> agent selects dependency files
-> parse dependencies
-> agent proposes dependency changes
-> user reviews changes
-> generate artifacts
-> write report
-> stop
```

### Deterministic steps

- collect input
- validate provider config
- clone or copy repos
- scan manifests and setup clues
- parse supported manifests
- record review outcomes
- generate artifacts
- write `report.json`

### Agentic steps

- select which dependency files should be used
- propose structured dependency changes

The agent never executes tools or shell commands directly.

## Supported Inputs

RepoResolve currently parses:

- `requirements*.txt`
- `environment.yml`
- `environment.yaml`
- environment-like `.yml` and `.yaml`

It also detects but does not parse some unsupported formats, including:

- `requirements*.in`
- `pyproject.toml`
- `setup.py`
- `setup.cfg`
- `Pipfile`
- `poetry.lock`
- `uv.lock`

It also scans for setup clues in files such as:

- `README.md`
- `Dockerfile`
- GitHub Actions workflows
- shell scripts in `extras/` and `scripts/`
- `install_*.sh`

## Generated Artifacts

Each run creates:

```text
./artifacts/<run_id>/
```

Files:

- `environment.generated.yml`
- `manual-setup.md`
- `manual-setup.json`
- `report.json`

`report.json` is the machine-readable summary of the run.

## Doctor Workflow

`reporesolve doctor` validates the latest generated run in the current directory.

Flow:

```text
load latest run
-> verify artifacts exist
-> verify conda is available
-> validate manual setup clues where possible
-> run conda solve validation
-> optionally run install validation
```

It checks:

- artifact presence
- `conda` availability
- environment visibility
- manual prerequisite clues
- solve validation with `conda env create --dry-run`
- optional disposable install validation with `reporesolve doctor --install`

## Key Models

- `ToolResult`
  - standard result for deterministic tools
- `SessionState`
  - TUI and supervisor state
- `DependencySelection`
  - agent output for manifest choice
- `AgentDecision`
  - agent output for dependency resolution proposals

## Storage and Config

Run-scoped paths are relative to the directory where RepoResolve is invoked:

- clones: `./repos/`
- artifacts: `./artifacts/<run_id>/`

`REPORESOLVE_WORKDIR` can override the working directory used for repos and artifacts.

Settings are loaded from:

1. `.env`
2. `~/.reporesolve/config.json`
3. environment variables

Later sources override earlier ones.

## Current Limits

Intentional `v0` limits:

- no automatic system package installation
- no automatic CUDA, MuJoCo, or OpenGL setup
- no full install-and-run loop from `reporesolve`
- no public resume flow
- no parsing for unsupported dependency formats

Some future-facing structures already exist, but are not part of the public `v0` flow:

- `main_repo` is collected but not yet used in planning
- `history` exists but is lightly used
- planner methods for later repair loops already exist
- standalone `build`, `install`, and `smoke` tools exist but intentionally fail honestly outside the main flow

## Summary

RepoResolve is a guided artifact generator plus a validator.

Main flow:

1. inspect and understand the repos
2. let the agent choose and resolve Python-level dependencies
3. let the user review conflicts
4. generate editable outputs
5. validate them with `doctor`

That generation-first, validation-second split is the core architecture of the project.
