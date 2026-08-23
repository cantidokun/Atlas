# OpenHands Transition Guide

This guide records the planned transition from the current ChatGPT/GitHub/local-machine Atlas development workflow to an OpenHands-assisted local development workflow.

## Core rule

Keep **Atlas-Unreal-Aider** and the **Blender Agent** as separate repositories. OpenHands may eventually work across both repositories from one controlled local workspace, but the repositories must not be merged merely to enable agent coordination.

## Target workspace

```text
C:\Atlas-Development\
│
├── Atlas-Unreal-Aider\
│   └── .git\
│
└── Blender-Agent\
    └── .git\
```

Each repository retains its own Git history, dependencies, issues, CI, release process, and development environment. Cross-system integration should use explicit interfaces/contracts.

## Current Atlas checkout

The Atlas-Unreal-Aider checkout has historically been:

```text
C:\Users\Gavin's PC\Desktop\Atlas-Unreal-Aider
```

Verify the actual path before beginning the transition.

## Transition sequence

### 1. Prepare a safe environment

Do not give OpenHands unrestricted access to the Windows machine. Start with a disposable workspace, then the Atlas repository, and only later add broader Unreal/Blender capabilities.

### 2. Install WSL 2

Verify:

```powershell
wsl --version
```

If needed:

```powershell
wsl --install -d Ubuntu
```

Verify:

```bash
wsl --list
```

Confirm current OpenHands/Windows requirements when the transition begins.

### 3. Install Docker Desktop

Use Docker Desktop for Windows with the WSL 2 based engine enabled.

Then enable the Ubuntu distribution under:

**Settings → Resources → WSL Integration**

### 4. Install OpenHands

Use the current official OpenHands installation method. The command expected when this guide was created was:

```bash
uv tool install openhands --python 3.12
```

Verify:

```bash
openhands --help
```

OpenHands installation commands may change; verify current documentation at transition time.

### 5. Test with a disposable directory

Create:

```powershell
mkdir C:\Atlas-OpenHands-Test
```

Then in WSL:

```bash
cd /mnt/c/Atlas-OpenHands-Test
```

Use OpenHands' current local-workspace/mount procedure. The historical command was:

```bash
openhands serve --mount-cwd
```

Verify that:

- OpenHands launches.
- The LLM connection works.
- The agent can see the mounted workspace.
- The agent can create and modify files.
- Changes appear on the Windows host.
- Docker/WSL isolation behaves as expected.

Do not connect the production Atlas repository or Unreal during this phase.

### 6. Connect Atlas-Unreal-Aider

After the disposable test succeeds:

```bash
cd "/mnt/c/Users/Gavin's PC/Desktop/Atlas-Unreal-Aider"
git status
git branch --show-current
```

Before any modification, confirm the correct branch and working-tree state.

First agent tasks should be read-only:

> Inspect the Atlas repository and report the current Git branch, working-tree status, repository structure, major development documentation, and current architectural areas. Do not modify anything.

Then:

> Identify the current Atlas planning/runtime architecture and list the relevant files and relationships. Do not modify anything.

### 7. Establish Atlas operating rules

OpenHands should follow these rules:

1. Preserve repository boundaries.
2. Do not merge Atlas-Unreal-Aider with the Blender Agent.
3. Treat C++ interoperability as a core Atlas architectural requirement.
4. Prefer language-neutral subsystem contracts.
5. Avoid unnecessary Python-specific coupling in core contracts.
6. Keep Python for AI, reasoning, orchestration, experimentation, and suitable tooling.
7. Keep performance-sensitive components viable for future C++ implementations.
8. Preserve authorization and runtime boundaries.
9. Never weaken tests solely to make a change pass.
10. Prefer solving established GitHub issues instead of creating unnecessary parallel work.
11. Avoid unrelated modifications.
12. Inspect current documentation and issue history before major architectural changes.
13. Make coherent, reviewable commits.
14. Do not reset, discard, or overwrite unrelated user work.
15. Preserve system safety and human-control boundaries.
16. Prefer incremental changes over speculative rewrites.

## C++ interoperability requirement

Atlas should evolve as a Python-first/hybrid system rather than as a Python implementation that later requires a wholesale rewrite.

Python is appropriate for:

- AI/LLM interaction
- reasoning
- high-level planning
- orchestration
- experimentation
- tooling
- Blender automation where Blender's Python API is the appropriate interface

C++ should remain viable for:

- performance-critical runtime components
- geometry and spatial computation
- high-performance vision
- simulation
- concurrency
- GPU-facing systems
- Unreal integration
- other performance-sensitive execution paths

Prefer:

```text
Python implementation
        ↓
Language-neutral contract
        ↓
C++ implementation
```

over Python-specific assumptions that make later native replacement difficult.

## Progressive access model

### Level 1 — Source access

OpenHands can inspect and modify the Atlas source repository, use Git, and update documentation.

### Level 2 — Build/test access

Add compilers, unit tests, static analysis, and other deterministic validation.

### Level 3 — Unreal access

Only after Levels 1–2 are reliable. Determine which Unreal operations can run inside the OpenHands environment and which require a controlled host-side bridge.

### Level 4 — Broader production execution

Do not enable unrestricted external/production authority merely to simplify development. This requires separate architectural and security review.

## Unreal execution boundary

OpenHands having access to a local repository does not automatically mean it can safely control every Windows application.

Determine:

1. Which Atlas builds run inside OpenHands.
2. Which tests run there.
3. Which Unreal commands require the Windows host.
4. Whether a controlled host-side bridge is needed.
5. What permissions the bridge requires.
6. How results return to OpenHands.

Do not weaken Docker/WSL isolation just to make Unreal access convenient.

## Git discipline

Before work:

```bash
git status
git branch --show-current
```

Before substantial edits:

- confirm repository and branch
- inspect relevant issues/docs
- understand existing local changes

After work:

```bash
git status
git diff
```

Do not overwrite unrelated local work. Do not reset or discard user changes without explicit authorization.

## Eventual autonomous development loop

Once the environment is mature, a high-level task may look like:

> Continue Atlas development toward the next established milestone. Inspect the current issues and repository state, determine the highest-priority solvable item, implement it, run the appropriate tests, fix failures, update documentation, and commit the completed work. Do not modify the Blender repository unless the change genuinely crosses an established contract.

Desired loop:

```text
Inspect
  ↓
Determine next work
  ↓
Implement
  ↓
Test
  ↓
Diagnose
  ↓
Fix
  ↓
Retest
  ↓
Update documentation
  ↓
Commit
  ↓
Continue
```

Human oversight remains appropriate for major architecture, destructive operations, production access, and significant cross-system changes.

## Long-term division of labor

```text
                    YOU
                     │
          Architecture / priorities
                     │
                     ▼
                 ChatGPT
                     │
             reasoning / review
                     │
                     ▼
                OpenHands
                     │
        implementation / execution
                     │
       ┌─────────────┴─────────────┐
       │                           │
Atlas-Unreal-Aider            Blender Agent
       │                           │
    Unreal                      Blender
       │                           │
       └─────────────┬─────────────┘
                     │
                 GitHub
```

- ChatGPT: architecture, strategic reasoning, difficult design decisions, review, and planning.
- OpenHands: persistent implementation, repository operations, local builds/tests, and iterative debugging.
- GitHub: source control, issues, branches, commits, pull requests, and history.
- Unreal/Blender: actual execution environments.

## Transition checklist

### Preparation

- [ ] Confirm current Atlas-Unreal-Aider path.
- [ ] Confirm working-tree state.
- [ ] Confirm branch.
- [ ] Confirm GitHub access.
- [ ] Install/verify WSL 2.
- [ ] Install/verify Docker Desktop.
- [ ] Verify Docker WSL integration.
- [ ] Install/verify OpenHands.
- [ ] Configure the selected LLM provider/model.

### Safe validation

- [ ] Test OpenHands using a disposable directory.
- [ ] Verify file mounting.
- [ ] Verify edits appear on the Windows host.
- [ ] Verify Git commands work.
- [ ] Verify the agent does not access unrelated files.

### Atlas connection

- [ ] Connect Atlas-Unreal-Aider.
- [ ] Perform read-only inspection.
- [ ] Verify branch and working-tree awareness.
- [ ] Add Atlas operating rules.
- [ ] Test a small reversible change.
- [ ] Build/test it.
- [ ] Review the Git diff.
- [ ] Commit only after verification.

### Expanded environment

- [ ] Determine available Unreal operations.
- [ ] Establish any controlled Unreal bridge.
- [ ] Add Blender-Agent as a second independent repository only when ready.
- [ ] Define/verify cross-repository contracts.
- [ ] Test cross-repository awareness without merging repositories.

### Autonomous operation

- [ ] Establish issue-selection rules.
- [ ] Establish branch/commit rules.
- [ ] Establish test requirements.
- [ ] Establish human-approval boundaries.
- [ ] Establish failure/recovery behavior.
- [ ] Establish production-access restrictions.
- [ ] Begin with bounded autonomous tasks.
- [ ] Increase autonomy only after reliability is demonstrated.

## Important principles

### Keep repositories separate

The Unreal and Blender projects remain separate repositories.

### Keep interfaces stable

Cross-system communication should use explicit contracts rather than shared implementation assumptions.

### Keep C++ migration possible

Do not allow Python implementation details to become permanent architectural contracts.

### Keep humans in control of high-impact decisions

Autonomy should increase progressively.

### Prefer solving issues

Use the established GitHub issue backlog and solve appropriate issues rather than indefinitely deferring them.

### Preserve development safety

A more autonomous agent does not mean unrestricted access to the entire Windows machine.

## Reference note

This guide describes the planned transition as of August 2026. OpenHands, Docker, WSL, and related tooling may change. Verify current installation/configuration instructions from official documentation when the transition begins.

The architectural principles in this document are more important than any specific installation command.
