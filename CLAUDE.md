# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Overview

Personal research project: dynamics of a rotating, cable-connected space station for artificial gravity. It started as a generic study (three 1 600 t cylindrical modules, 0.38 g at 1 rpm) and converged on a concrete mission, the **retained solution**:

- Three SpaceX Starships, **vertical** (long axis radial, nose toward the spin centre), in a **triangle**, on the Earth→Mars Hohmann transfer (259 days). One crew ship, two cargo ships.
- Each ship is attached by its nose at two points ±3.5 m apart, each cable going to the neighbour on its side (bridle effect: restores roll).
- Cables sized for full ships (1 600 t) at 1 g with safety factor 3 (Dyneema, 90.6 cm²). Dynamics computed at **610 t** per ship (mass after trans-Mars injection, 560–650 t range).
- Target gravity: Mars surface **3.711 m/s²** at **1 rpm** → R = 338.4 m at the ships' centre of mass.
- Propellant slosh modelled (Abramson pendulums), tanks with **baffles** (ζ = 3 %).
- **Tuned liquid damper**: 25 t water pool, Ø 7.2 m × 0.61 m, floor 12 m from the nose, tuned to 0.117 Hz, ζ = 0.15. Cuts the worst out-of-plane resonance from 2.7° to ≈ 0.45°.

- **Cable-break safety** (notebook § 7): best simulated parade = two half-section strands per side, same cable mass (`--side-strands 2`, campaign `brins`, § 7.4), plus cutters that drop the broken strand's pieces (`--release-delay 1`). A hub (20 t) tied to each nose by two spokes (`--hub-mass-t 20 --hub-spokes 2`, campaigns `rupture`, `moyeu`, § 7.3) also covers the loss of a whole side; it does not change comfort.
- **Other studies on top of the retained solution**: spin-up from 0.1 to 1 rpm with α = k·ω² (`--spin-from`, campaign `montee`, § 5.4); LOX baffles at ζ = 8 % for the remaining LOX peak (campaign `lox`, `lox_search.py`, § 6.2); unequal masses after a propellant transfer (`--masses-t 220,805,805 --attach-x 9 --target-ship 0 --rpm 0.87`, campaign `masses`, § 5.5): the crew ship becomes ~6× more sensitive.

Rejected alternatives (keep as chapters, don't reopen unless asked): two ships (roll about the cable is neutral, drifts freely), horizontal ships (need masts, worse resonances), generic modules (preliminary study).

Running list of open questions and future work: `TODO.md`. Results summary: `README.md`.

## Conventions

- The user writes comments, CLI help, UI strings and the pages in **French**; keep that for code and docs in this repo. Commit messages: compact one-line English, no model attribution, no Co-Authored-By trailer.
- **Commit as you go**: commit each coherent step (code change, campaign results, page update) without waiting to be asked. Remote `origin` = public GitHub repo; push only when the user asks.
- The Mac is often in use: run long computations at low priority (`nice -n 19`), few in parallel (`--jobs 2`), in the background. Several hours of compute are acceptable.
- `tether_sim.py` is the single source of the physics. `run_scenarios.py` holds the scenario catalogues (`CAMPAIGNS`). Keep both self-contained (NumPy + Matplotlib only) so they run in either venv.
- When changing a motion program or a diagnostic, re-run the affected campaign and `make_web_data.py`; the pages read everything from `docs/data/`.
- Page numbers quoted in prose must come from `docs/data/summary.json` (prefer `data-bind` spans) or from a script output; re-check them after any re-run.

## Files

| File | Role |
|---|---|
| `tether_sim.py` | Simulator: rigid ships (`starship_mass_model`: element mass model, slosh pendulums, optional water pool `tld=`), discretised unilateral cables, prescribed internal masses, Kane damper; options: hub and spokes (`--hub-*`), cable break and piece release (`--break-*`, `--release-delay`), strands per side (`--side-strands`, `--strand-gap`), spin-up thrust (`--spin-*`), unequal masses (`--masses-t`, `--attach-x`, `--target-ship`), second pool (`--tld2-*`) |
| `run_scenarios.py` | Campaigns: `rotation`, `internes`, `final` (generic study), `starship`, `mission`, `ballottement`, `retenue`, `amortisseur`, `rupture`, `brins`, `moyeu`, `montee`, `lox`, `masses` |
| `mission_mass.py` | Starship mass after trans-Mars injection |
| `slosh_modes.py` | Linear out-of-plane model (attachment, tilt, slosh pendulums): coupled modes |
| `tld_design.py` | Damped linear model integrated in time (same sweep program as the simulator): TLD design search |
| `lox_search.py` | Same linear model: stronger LOX baffles or a second pool against the coupled LOX mode |
| `chrono_validation.py` | Cross-validation with Project Chrono (PyChrono 10) |
| `make_web_data.py` | Export to `docs/data/` (summary, series incl. sweep curves, 3D animations listed in `ANIMATIONS`) |
| `docs/grand-public/`, `docs/technique/` | The two pages; `docs/shared/` = three.js viewer, SVG charts, schemas |
| `docs/stage_publish.sh` | Copies each page + only the data it uses into a publish folder |

## Environments

- `.venv/` (NumPy, SciPy, Matplotlib): simulator, campaigns, export. Use full paths, e.g. `.venv/bin/python run_scenarios.py retenue`.
- `tools/chrono-env/` (PyChrono 10.0.0, created with a project-local micromamba in `tools/bin/`): only for `chrono_validation.py`. The system miniconda in `~/miniconda3` is broken; do not use it.
- Campaigns run one process per scenario (`--jobs`). A 5 460 s sweep with slosh takes ~1.5 h per scenario.

## Outputs and publishing

- `out/<campaign>/`: per-scenario `.log`, `.json` (inputs + results), `.npz` (time series), optional `_traj.npz` (3D trajectories), plus `summary.md`. Git-ignored; reproducible. `out/tld_search.{log,json}`: TLD search.
- `docs/data/`: exported JSON consumed by the pages (committed).
- Local preview: `docs/_preview/build.sh`, then `python3 -m http.server 8765` in `docs/_preview/`; headless Chrome `--dump-dom` to check that charts render and bound values fill in.
- Public static site: http://t.baeckeroot.free.fr/tethered-station/ — built by `docs/build_site.sh <dir>` (adds the HTML skeleton, rewrites the Artifact links to relative ones); the user copies it to free.fr. The repo is public on GitHub: no secrets, no work identifiers. Code is MIT (`LICENSE`), page content CC BY 4.0 (`docs/LICENSE`).
- Also published as private claude.ai Artifacts, used as previews (same URLs on every update):
  - grand public: https://claude.ai/artifact/AhFHVxf86G4P5S4H4s9cXx
  - carnet technique: https://claude.ai/artifact/5dVec5xiSvaZwkLvLzXFMi
- To republish: `docs/stage_publish.sh <scratch dir>`, then Artifact publish with `url`, `file_path=<dir>/<page>/index.html`, `root=<dir>/<page>` and `files` = the changed data files (new `data/series/*.json`, `data/anim/*.json`, `data/summary.json`). In a new session, first `list` the artifact with `scope: "files"` (a publish touching unread files is refused). New page data must also be added to `stage_publish.sh` (grand public copies only listed files).

## Physics pitfalls already met

- Rotating-frame relaxation: whole-system translation is unstable (centrifugal on an offset centre of mass); the centre of mass is re-centred every step.
- Explicit cable damping is unstable for realistic c/m; damping is applied exactly (exponential decay per segment) after each step.
- Prescribed internal motions must have bounded acceleration: an instantaneous reversal shows up as a large horizontal jolt in the felt gravity.
- Slosh damping acts on the pendulum velocity **relative to the wall**, L(φ̇ − θ̇), not on the absolute angle.
- Felt floor tilt = ship tilt + lateral acceleration of the ship's centre of mass / local g (θ + ü/g). Sanity check: a free simple pendulum feels zero tilt. A sign error here once gave 0.69° instead of ≈ 2.7°.
- The structure is nearly undamped: steady-state frequency response is meaningless (81° peaks); use the time-domain sweep. The linear model, without cable damping, is conservative by 15–50 % against the simulator.
- Sweep curves (`sweep_response`, `tld_design.sweep`) must use **contiguous** time windows per frequency. Narrow ±10 s windows spaced ~135 s apart once missed the peaks (2.25° plotted vs 2.67° true).
- After a cable break without hub, ships tumble and cables would wrap around the noses: the model has no cable–hull contact, so only the first minutes are quantitative.
- Diagnostics that sum over all masses (L/I, centre of mass) break down once pieces are released and fly away; the spin rate and the diagnostic centre (distances to centre, roll) use the ships, internal masses, propellant and hub only, not the cable nodes.
- In shell heredocs that embed JavaScript, quote the delimiter (`<<'EOF'`) or write a script file: backticks and `${}` would otherwise be executed by the shell.
- `tilt_max` in summaries is the global maximum over the run; sweep-curve peaks are per-frequency maxima. Don't mix them when quoting a "peak at f Hz".
