# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Overview

Personal research project: dynamics of a rotating, cable-connected space station for artificial gravity (massive modules, 0.38 g at 1 rpm, R = 340 m, high orbit). Pure-Python simulator plus Project Chrono cross-validation, and two HTML publications under `docs/`.

## Conventions

- The user writes comments, CLI help and UI strings in French; keep that for code and docs in this repo.
- `tether_sim.py` is the single source of the physics. `run_scenarios.py` holds the scenario catalogues (`CAMPAIGNS`). Keep both self-contained (NumPy + Matplotlib only) so they run in either venv.
- When changing a motion program or a diagnostic, re-run the affected campaign and `make_web_data.py`; the pages read everything from `docs/data/`.

## Environments

- `.venv/` (NumPy, Matplotlib): simulator, campaigns, export. Use full paths, e.g. `.venv/bin/python run_scenarios.py rotation`.
- `tools/chrono-env/` (PyChrono 10.0.0, created with a project-local micromamba in `tools/bin/`): only for `chrono_validation.py`. The system miniconda in `~/miniconda3` is broken; do not use it.
- Campaigns run one process per scenario (`--jobs`, default 9 on the 10-core M1 Max). Long sweeps take ~25 min.

## Outputs

- `out/<campaign>/`: per-scenario `.log`, `.json` (inputs + results), `.npz` (time series), optional `_traj.npz` (3D trajectories), plus `summary.md` and `comparaison.png`. Git-ignored; reproducible.
- `docs/data/`: exported JSON consumed by the pages.
- `docs/_preview/build.sh` builds local preview copies (adds the charset the publish skeleton normally provides); serve `docs/_preview/` with `python3 -m http.server`.

## Physics pitfalls already met

- Rotating-frame relaxation: whole-system translation is unstable (centrifugal on an offset centre of mass); the centre of mass is re-centred every step.
- Explicit cable damping is unstable for realistic c/m; damping is applied exactly (exponential decay per segment) after each step.
- Prescribed internal motions must have bounded acceleration: an instantaneous reversal shows up as a large horizontal jolt in the felt gravity (artefact seen with the first walk and sweep programs).
