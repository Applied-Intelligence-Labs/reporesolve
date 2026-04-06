# RepoResolve

RepoResolve is an agentic supervisor system that builds and repairs multi-repository environments. It guides you through input collection, analyzes dependency metadata, and iteratively proposes environment changes using a reasoning agent while deterministic tools execute the steps.

## What It Solves
- Bootstrapping a working environment across multiple repos
- Identifying dependency conflicts and setup failures
- Iteratively refining environment proposals until smoke tests pass

## Quickstart
```bash
pip install -e .
reporesolve
```

## Example Output (Trimmed)
```
RepoResolve - Starting supervisor run...
Cloning repos... OK
Inspecting repos... OK
Parsing dependencies... OK
Attempt 1/3
Build... OK
Install... OK
Smoke tests... OK
Success
```

## How the Agent Loop Works (High Level)
1. Tools inspect repositories and parse dependencies.
2. The agent proposes an environment decision in strict JSON.
3. Tools build/install/test the environment.
4. Failures are summarized and sent back to the agent for revision.
5. The loop stops on success, agent stop, or max attempts.

## Configuration
RepoResolve reads API keys from `.env` (if present) or environment variables.

Example `.env`:
```
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
```

## Commands
- `reporesolve` (start guided flow)
- `reporesolve start`
- `reporesolve config`
- `reporesolve resume`
- `reporesolve doctor`
- `reporesolve version`
