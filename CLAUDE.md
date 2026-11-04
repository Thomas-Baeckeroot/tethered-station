# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Overview

Personal research project: dynamics of a rotating, cable-connected space station for artificial gravity. It started as a generic study (three 1 600 t cylindrical modules, 0.38 g at 1 rpm) and converged on a concrete mission, the **retained solution**:

- Three SpaceX Starships, **vertical** (long axis radial, nose toward the spin centre), in a **triangle**, on the Earth→Mars Hohmann transfer (259 days). One crew ship, two cargo ships.
- Each ship is attached at the two Starship V3 catch points on the nosecone flanks, **13 m from the tip, ±4.8 m from the axis** (h = 21 m above the centre of mass; estimated from photos, notebook § 2.5; `tether_sim.ANCHOR_X`, `ANCHOR_SPREAD`, used by every campaign and linear model), each cable going to the neighbour on its side (bridle effect: restores roll). Internal reinforcement for the 30° side pull is assumed. Before 2026-11-01 the anchors were at 9 m from the tip, ±3.5 m (h = 25 m).
- Cables sized for full ships (1 600 t) at 1 g with safety factor 3 (Dyneema, 90.6 cm²). Dynamics computed at **610 t** per ship (mass after trans-Mars injection, 560–650 t range).
- Target gravity: Mars surface **3.711 m/s²** at **1 rpm** at the **main deck**, 14 m from the nose (`--g-ref-x 14`, R = 338.4 m there); the ships' centre of mass (34 m from the nose) turns at R = 358.4 m, cables 578.7 m unloaded (579.6 m loaded), 1.39 MN each. Before 2026-10-31 the target was at the centre of mass (deck at 3.49 m/s²). Simulator gravity diagnostics (`g_min`/`g_max`) are at the ship's centre of mass, 6 % above the deck value.
- Propellant slosh modelled (Abramson pendulums), tanks with **baffles** (ζ = 3 %).
- **Tuned liquid damper**: 25 t water pool, Ø 7.8 m × 0.52 m, floor 12 m from the nose, tuned to 0.103 Hz, ζ = 0.15 (`tether_sim.POOL`). Cuts the worst out-of-plane resonance to ≈ 0.43° (LOX coupled mode at 0.26 Hz). The worst in-plane sweep peak, 0.55° at 0.34 Hz, is the cable-stretch mode; the stiffer SK99 cable moves it out of the band.

- **Cable-break safety** (notebook § 7), retained since 2026-11-01: **three third-section strands per side**, same cable mass (30.2 cm², Ø 6.2 cm each; `--side-strands 3`), plus cutters that drop a broken strand's pieces (`--release-delay 1`); campaign `brins3`, § 7.4, incl. a second break on the same side (`--break-cable2`, `--break-time2`; cable index = strand × 3 + side). One break: remaining two at 7.7 % of strength en route, 50 % in the design case (factor 2); two breaks: last strand at 15 % en route. The strands sit on a triangular plate on a ball joint at each nose fitting (equal sharing after a break, no mutual shading; not modelled, equivalent to a common fitting). Two half-section strands (campaign `brins`, § 7.5) were the earlier study: all strands of a side must leave from that side's fitting, since roll about the ship axis is held only by the bridle effect (`--strand-layout`). A hub (20 t) tied to each nose by two spokes (`--hub-mass-t 20 --hub-spokes 2`, campaigns `rupture`, `moyeu`, § 7.3) is the alternative that also covers the loss of a whole side or fitting (38 t); it does not change comfort.
- **Sun pointing** (notebook § 5.6, `sun_pointing.py`, campaign `soleil`): the spin axis follows the Sun (180° over the transfer) with out-of-plane pulses at the line of nodes (`--precess-rate`, `--precess-pulse`; 66–94 t hot-gas propellant). Fixed panels on the lit side; the heat-shield tiles stay in shade and radiate, so the propellant does not boil off (it needs ~1 kW of heating). A fixed axis would let sunlit tiles boil it off.
- **Other studies on top of the retained solution**: spin-up from 0.1 to 1 rpm with α = k·ω² (`--spin-from`, campaign `montee`, § 5.4); LOX baffles at ζ = 8 % for the remaining LOX peak (campaign `lox`, `lox_search.py`, § 6.2); unequal masses after a propellant transfer (`--masses-t 220,805,805 --target-ship 0 --rpm 0.8621` with the catch-point anchors, campaign `masses`, § 5.5): the crew ship becomes ~7× more sensitive, and the crew walk (16 s round trip) hits its 0.06 Hz sway. Partial transfers and a low ballast (`--ballast-t/-x/-ship`, campaign `allege`, `light_tld.py`): its out-of-plane sway slows down and leaves the pool tuning; a retuned pool (Ø 8.8 m) brings half transfer, or full transfer + 50 t ballast, back to ≈ 0.6–0.7° at the worst rhythm. Sensitivity (campaign `sensibilite`, § 6.3): full V3 ships (693 t en route) and a realistic braided, sheathed, redundant SK99 cable (`--material sk99`, 136 cm², 25 t): same comfort. With unequal masses, read the crew ship's values (`tilt_max_ship[0]`, added by `make_web_data.py`): the global `tilt_max` includes the cargo ships' static pivot.

- **Snap-back of a broken strand** (notebook § 7.4, campaign `entretoises`, `snapback.py`): once slack, the near half of a broken strand drifts outward and backward (Coriolis) and sweeps across the hull of the ship whose fitting is on the leading side, 3–4 s after the break, cutters or not. A boom (attachments at ±16 m) only delays it; a lanyard (`--release-keep 0`) makes it hang against the hull. Ties between the three strands of a side every 24–48 m (`--strand-ties N --tie-slack 0.1 --tie-k 2.6e7 --release-delay -1`, 48 segments) hold it: no contact, softer jolt; each tie carries about one strand tension. Peak values of the loose ends between ties depend on the discretisation.
- **Real load cases and creep** (notebook § 2.6): the 1 600 t at 1 g sizing case never occurs; it is kept because creep over 2 × 259 days and strand breaks give about the same section. Return ramped up to 1 g with 250 t ships (campaign `retour`, `--mass-t 250 --accel 9.81 --rpm 1.626`): same side tension as outbound (1.46 MN). Realistic SK99 braid: 0.31 % creep at 20 °C over the round trip (cold cable: negligible, Arrhenius extrapolation unproven).

Rejected alternatives (keep as chapters, don't reopen unless asked): two ships (roll about the cable is neutral, drifts freely), horizontal ships (need masts, worse resonances), generic modules (preliminary study).

Running list of open questions and future work: `TODO.md`. Results summary: `README.md`.

## Conventions

- The user writes comments, CLI help, UI strings and the pages in **French**; keep that for code and docs in this repo. Commit messages: compact one-line English, no model attribution, no Co-Authored-By trailer.
- **Commit as you go**: commit each coherent step (code change, campaign results, page update) without waiting to be asked. Remote `origin` = public GitHub repo; push only when the user asks.
- The Mac is often in use: run long computations at low priority (`nice -n 19`), few in parallel (`--jobs 2`), in the background. Several hours of compute are acceptable.
- `tether_sim.py` is the single source of the physics. `run_scenarios.py` holds the scenario catalogues (`CAMPAIGNS`). Keep both self-contained (NumPy + Matplotlib only) so they run in either venv.
- When changing a motion program or a diagnostic, re-run the affected campaign and `make_web_data.py`; the pages read everything from `docs/data/`.
- Both page footers end with « Dernière révision : YYYY-MM-DD » : update the date whenever a page's content changes.
- Page numbers quoted in prose must come from `docs/data/summary.json` (prefer `data-bind` spans) or from a script output; re-check them after any re-run.

## Files

| File | Role |
|---|---|
| `tether_sim.py` | Simulator: rigid ships (`starship_mass_model`: element mass model, slosh pendulums, optional water pool `tld=`), discretised unilateral cables, prescribed internal masses, Kane damper; options: hub and spokes (`--hub-*`), cable break and piece release (`--break-*`, second break `--break-cable2`/`--break-time2`, `--release-delay`, `--release-keep`), strand ties (`--strand-ties`, `--tie-*`), strands per side (`--side-strands`, `--strand-gap`, `--strand-layout`), spin-up thrust (`--spin-*`), axis pivot toward the Sun (`--precess-*`), unequal masses (`--masses-t`, `--attach-x`, `--target-ship`), low ballast (`--ballast-*`), second pool (`--tld2-*`), gravity reference point along the ship (`--g-ref-x`), cable material (`--material`, incl. `sk99`) |
| `run_scenarios.py` | Campaigns: `rotation`, `internes`, `final` (generic study), `starship`, `mission`, `ballottement`, `retenue`, `amortisseur`, `rupture`, `brins`, `moyeu`, `montee`, `lox`, `masses`, `soleil`, `allege`, `sensibilite`, `brins3`, `retour`, `entretoises` |
| `mission_mass.py` | Starship mass after trans-Mars injection |
| `slosh_modes.py` | Linear out-of-plane model (attachment, tilt, slosh pendulums): coupled modes |
| `tld_design.py` | Damped linear model integrated in time (same sweep program as the simulator): TLD design search |
| `sun_pointing.py` | Sun pointing: Sun direction on the transfer, axis-pivot impulse, 2D tank heat balance by orientation and coverings → `docs/data/soleil.json` |
| `lox_search.py` | Same linear model: stronger LOX baffles or a second pool against the coupled LOX mode |
| `meteorites.py` | Meteoroid cuts per trip (Grün flux) for a single cable or N strands per side → `out/meteorites.log` (notebook § 7.1) |
| `cable_thermal.py` | Cable thermal balance with the axis toward the Sun: sheath equilibrium temperatures, time constant, lit/shaded face gradient across the section and the strain mismatch → `out/cable_thermal.log` (`--brins N` for one of N strands) |
| `light_tld.py` | Same linear model generalised to unequal masses (crew ship radius, cable tension and length from the simulator): lightened crew ship modes, pool retune search → `out/light_tld.json` (exported into `docs/data/allege.json`) |
| `creep.py` | Cable creep over the round trip (Eyring law calibrated on published DSM data for SK75/SK78/DM20, cable temperature along the transfer, return ramped up to 1 g with 250 t ships from campaign `retour`) → `out/creep.log`, `docs/data/creep.json` (notebook § 2.6) |
| `snapback.py` | Broken-strand path in ship 0's frame (campaign `entretoises`) → `docs/data/snapback.json` (notebook § 7.4) |
| `deploy_sim.py` | Cable payout on top of `tether_sim.Station`: variable rest length and node mass; modes free, thrust law ω ∝ r^(−p), launch and brake (tension servo) → `out/deploiement/` (not yet exported; keep lateral thrust well below the axial acceleration, the slosh pendulums leave their domain otherwise) |
| `chrono_validation.py` | Cross-validation with Project Chrono (PyChrono 10): generic modules, and the retained Starship solution (slosh bobs on stiff damped rods, lateral wall damping, unilateral cables, cable break and release); outputs in `out/validation/` |
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
- Local preview: `docs/_preview/build.sh`, then `python3 -m http.server 8765 --bind 127.0.0.1` in `docs/_preview/` (localhost only, never all interfaces); headless Chrome `--dump-dom` to check that charts render and bound values fill in.
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
- The 3D viewer redraws cable chains at each event: the break (`anim.cut`) and the cutter release (`anim.release`). Without the latter, the cut attachment segments are still drawn and the released pieces look like they stretch back to the ships.
- `make_web_data.py` treats every `.json` in `out/<campaign>/` as a scenario: keep ad-hoc analysis outputs elsewhere (scratch dir).
- Fixed-period resonance scenarios (`RESO` 3.89 s for the LOX coupled mode, `RESO8`, `RESO_K`) must be retuned when the geometry changes: the LOX mode is lightly damped and very sharp (moving from 4.05 to 3.94 s dropped the free-slosh response from 3.0° to 1.8°). Scan the period with short runs before quoting a resonance.
- `tilt_max` in summaries is the global maximum over the run; sweep-curve peaks are per-frequency maxima. Don't mix them when quoting a "peak at f Hz".
