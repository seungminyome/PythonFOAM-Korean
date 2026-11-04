# Wrong-setup test 2: plan (fixed 2026-11-03, after the pilot)

Status: fixed. Committed and pushed before any model request is sent; after that, only the
Deviations section may change.

## Question

Can a vision-language model see, from two pictures of one state, that a run of the 2D step case was
set up wrong, and does it do better than rules on the same pictures?

The first test (2026-10-30) could not answer this: five wrong runs, one per kind of change, eight
correlated frames each, a one-number rule as the only competitor, and no scoring of the reason.

## Runs

- 30 base setups drawn by seed 20261103: inlet speed uniform in 20 to 40 m/s (one decimal),
  kinematic viscosity uniform in 1.0e-5 to 2.5e-5 m^2/s (three digits), start state one of the
  developed flow's written states t = 0.06, 0.07, 0.08, 0.09, 0.1 s.
- Each base is run twice: as written (normal, B<n>-N) and with one change (wrong, B<n>-W).
  The 30 changes, assigned to the bases in a seeded random order:

  | kind | parameter | count |
  |---|---|---:|
  | inlet_speed | factor 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 1.25, 1.5 on the base's speed | 8 |
  | viscosity | factor 0.1, 3, 5, 10, 20, 30, 100, 300, 1000 on the base's viscosity | 9 |
  | walls | lowerWall slip (4); lowerWall and upperWall slip (3) | 7 |
  | inlet_profile | lowest 0.25, 0.5, 0.75 of the inlet height at velocity 0 (each twice) | 6 |

  The draft had inlet_direction (4) and start_state (2) in place of 6 of these; the pilot showed
  that neither reaches the window, so their slots went to the other kinds (pilot section).
- pimpleFoam, OpenFOAM v2212, laminar, as the first test: 8,000 steps of 5e-6 s from t = 0.1 s,
  every 500th step written. A run that crashes, stops early or whose files do not hold the design's
  entries is refused by flow-check; the pair is then dropped, and the design records it.

## Frames and requests

- Three states per run: steps 6000, 7000 and 8000. Step 8000 is the primary frame; one run is one
  sample. Secondary frames are reported separately.
- Two conditions. stated: the note gives the base's intended inlet speed and viscosity (the same
  text for both runs of a pair). blind: it does not.
- Three variants of each request: t0 (temperature 0, seed 20261103), t07a and t07b (temperature 0.7,
  seeds 20261107 and 20261108). t0 is the main result; the others measure how far an answer moves.
- Model: Gemma 4 31B (QAT Q4_0, llama.cpp b11429, the settings of the first test). Other models
  only if time allows, after the 31B result is fixed.
- Reply: reason, assessment (consistent, inconsistent, cannot_tell), cause (none, inlet_speed,
  viscosity, walls, inlet_profile, inlet_direction, start_state, other).

## Scoring

- Right: a normal run answered consistent, a wrong run inconsistent. cannot_tell and no answer are
  wrong on both.
- Right for the right reason: right, and the cause is the run's own (none for a normal run).
- Primary score: right on the primary frames, out of 60 (or fewer if pairs were dropped).
- By kind of change: wrong runs caught, per kind.

## Baselines (no reference run; the same pictures and note)

- constant: consistent everywhere (30 of 60).
- peak rule: peak |U| in the window between 1 and 2 times the stated speed (stated condition only).
- labels: logistic regression on the colour-bar ends scaled by the stated speed (U max, U min,
  p min, p max) and the stated viscosity; leave-one-pair-out.
- labels + pixels: the same plus three pixel shares (slow-flow share of the |U| picture, how far
  along x the slow flow reaches in the lowest quarter, the low share of the p picture).
- pixels only: the three pixel shares (the blind condition's competitor).

## Statistics

- Exact McNemar test of the model against the strongest baseline on the same primary frames.
- 95 % bootstrap interval of the share right, resampling pairs.
- The conclusion "the model does better than the rules" needs p < 0.05 on the primary frames in
  the stated condition at t0. Anything else is reported as "not shown".

## Pilot (read before the design was fixed)

13 runs with seed 20261104 and other bases than the final set: three normal runs (20 m/s with
2.5e-5; 40 m/s with 1.0e-5; 30 m/s with 1.56e-5) and ten changes on the 30 m/s base (speed x0.7,
x1.5; viscosity x0.1, x10; lower wall slip; profile 0.25; direction +15, +30, -30; uniform start).
All 13 ended normally with the largest Courant number under 0.4 (jobs 25106856, 25106882).

Visibility, by the pictures at step 8000 (pilot/contact-8000.png) and by the window-averaged
difference of |U|/U0 from the 30 m/s normal run (pilot/visibility-arrays.txt; the same run's
own steps 6000 and 8000 differ by 0.107):
- walls (0.22) and viscosity x10 (0.14) change the shape of the flow: visible.
- speed x0.7, x1.5 and profile 0.25 keep the shape and change the colour-bar numbers (0.16,
  0.25, 0.15): visible through the labels, which the pictures carry.
- direction +15 (0.026), +30 and -30 (0.104) and the uniform start (0.080) are within the normal
  run's own movement: not visible. Both kinds are dropped.
- viscosity x0.1 (0.075) is also within that movement; the kind stays, as a hard item.
No pilot run is in the final set and no model saw a pilot frame.
## Deviations

- 2026-11-03, before any model request: B06-W (viscosity 0.0102 m^2/s, 1000 times the base's
  1.02e-5, on the base with 27.9 m/s) diverged in step 4643 (floating point exception, Courant
  number 7.7e16; job 25106926_11). As the plan says, the pair B06 is dropped: 29 pairs, 58 runs
  remain, viscosity 8 (factors 0.1, 3, 5, 10, 20, 30, 100, 300), walls 7. The `why` text in
  design.json's `dropped_pairs` names the change wrongly as slip walls; its `entries` hold the
  run's real change, and the file is left as the build hashed it. This note was corrected on
  2026-11-04, after the model answers, and changes no count.
