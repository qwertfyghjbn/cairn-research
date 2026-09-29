# M0 Cairn Baseline

## Status

M0 is complete for the local, model-free baseline path.

The research baseline is the exact upstream tree identified below. Research
changes must use `upstream_commit` as their comparison point; the package
version alone is not precise enough because the selected commit is 14 commits
after the `v0.2.1` tag.

## Frozen source

| Field | Value |
| --- | --- |
| Baseline ID | `cairn-main-8e7e0ea` |
| Upstream | `https://github.com/oritera/Cairn.git` |
| Upstream branch | `main` |
| Upstream commit | `8e7e0ea67552383851dfcabfba0c4e9c8d007878` |
| Commit timestamp | `2026-09-07T23:22:56+08:00` |
| Commit subject | `docs: add logo` |
| Package version | `0.2.1` |
| Nearest release | `v0.2.1-14-g8e7e0ea` |
| Selected on | `2026-09-29` |
| License | GNU Affero General Public License v3.0 |
| Dependency lock | `cairn/uv.lock` |
| Lock SHA-256 | `90c5a3cc9405e27e47bc9ae5e5681ab86c63e2a23afb7768fcf1b7aa1dc80ffb` |
| Worker image index | `ghcr.io/oritera/cairn-worker-container@sha256:d90d40b7c634b8d5dc9464e04b863a185b9efe964ffd2b246f6e5cbc2a2ef053` |
| Worker image linux/amd64 | `sha256:d41bd6922951e7237f0c1c2cd4451b4bb7d38cf373e2258ae00b841a71fcdfc2` |
| uv base image index | `ghcr.io/astral-sh/uv@sha256:c11a6b0892dcaafa4adfe89cc680117c955a8c55b107c2d432cee069b006cad8` |
| uv base image linux/amd64 | `sha256:68ab2a1582ea271691e440d537eb386cb506dd19196246a57f006223d6c62d1e` |

The public README describes the same Blackboard, Fact-Intent Graph,
Server/Dispatcher/Worker design referenced by the CRS project plan. This is
why `oritera/Cairn` was selected instead of other projects with the same name.

## Repository arrangement

- The upstream repository is checked out at `/home/lqs/cairn_research/cairn`.
- The upstream remote is named `upstream`.
- Research work starts on `research/v0-baseline`.
- No `origin` remote is configured because no user-owned fork URL has been
  provided. Add it only after a real fork exists.
- The original project plan remains at
  `/home/lqs/cairn_research/CRS_PROJECT_INIT.md`.

## Frozen toolchain inputs

- Python requirement: `>=3.12`
- Dependency resolver used for validation: `uv 0.11.6`
- Resolved interpreter used for validation: CPython `3.14.4`
- Dependency installation mode: `--frozen`
- Container definition: upstream `Dockerfile` and `docker-compose.yaml`
- Worker container tag in the upstream README:
  `ghcr.io/oritera/cairn-worker-container:latest`
- Application base image tag in the upstream Dockerfile:
  `ghcr.io/astral-sh/uv:python3.13-trixie`

The application dependencies are reproducibly pinned by `cairn/uv.lock`.
Both mutable container tags were resolved from GHCR on 2026-09-29. Experiments
must record the index digest above and `linux/amd64` as the platform. The
platform manifest digests are also recorded so the exact image can be audited
independently of index resolution. The upstream files remain unchanged.

## Reproduction commands

Run the checked-in verification wrapper from the repository root:

```bash
./scripts/verify_m0_baseline.sh
```

Equivalent upstream commands are:

```bash
UV_CACHE_DIR=/tmp/cairn-uv-cache \
  uv run --project cairn --frozen --group dev pytest -q

UV_CACHE_DIR=/tmp/cairn-uv-cache \
  uv run --project cairn --frozen cairn --help
```

The cache is placed under `/tmp` because the current managed workspace does
not permit writes to the default user cache directory.

## Validation evidence

Validation on 2026-09-29 produced:

```text
98 passed in 4.53s
```

The installed CLI exposed the expected `serve` and `dispatch` commands. A
server process also reached `Application startup complete` with an explicit
temporary SQLite path.

Docker is not installed in the current WSL environment. Therefore the Docker
Compose path and the external worker image were not executed in M0. This does
not block the local mock baseline: upstream's complete fast regression suite,
including mock end-to-end scheduler tests, passed without Docker or a live
model provider.

## M0 boundary

M0 made no changes to Cairn source, prompts, scheduling, Fact/Intent semantics,
worker count, termination behavior, or evaluator behavior. The only research
additions are this provenance record and the verification wrapper.
