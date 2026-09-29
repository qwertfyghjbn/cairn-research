# Cairn Research Workspace

This repository is rooted at the `cairn_research` workspace. The Cairn system
lives in `cairn/`; the project plan and benchmark selection live at the
workspace root.

```text
cairn_research/
├── CRS_PROJECT_INIT.md       Research plan
├── docs/benchmarks/          Benchmark selection and task registry
├── cairn/                   Cairn source, tests, and experiment protocol
└── cybench_repo/            Separate upstream clone; not tracked here
```

For a Windows host, clone into WSL2 and place Cybench beside `cairn/`:

```bash
git clone -b research/v0-baseline https://github.com/qwertfyghjbn/cairn-research.git cairn_research
cd cairn_research
git clone https://github.com/andyzorigin/cybench.git cybench_repo
git -C cybench_repo checkout ca483c6
```

The root `.gitignore` excludes `cybench_repo/`. It is an input to benchmark
planning, not a copy of Cybench in this repository. Cairn's own setup and
runtime instructions are in [cairn/README.md](cairn/README.md). Run Cairn
commands from the `cairn/` directory; for example, the frozen baseline check
is `./cairn/scripts/verify_m0_baseline.sh` from this root.

Start with [CRS_PROJECT_INIT.md](CRS_PROJECT_INIT.md) and
[the benchmark selection](docs/benchmarks/BENCHMARK_SELECTION_V1.md).
