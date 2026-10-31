# Notes on the pictures, written before any model saw them

One frame of each run was opened at full size (`U.png`, and `p.png` for most of them), at step
8,000 and for the wrong setups also at step 4,500. The set was built by job 24946942 from commit
`97db7eb`; no request has been sent. Nothing here changed a run, the question or the scoring.

| Run | Frames opened | What is in the pictures | Is the change visible? |
|---|---|---|---|
| N1 | step 8,000 U | Fast stream above y about 35 to 40 %, peak 37.02 m/s; below it a slow wake with thin dark lines and spots | No change in this run |
| N2 | step 6,000 U | The same picture as N1 at step 8,000 apart from the title (peak 37.02 m/s): one flow time, see below | No change in this run |
| N3 | step 4,500 p | A row of low-pressure cores at y about 25 to 35 %, -226 to 41 m^2/s^2 | No change in this run |
| N4 | step 5,500 U | As N1, peak 37.48 m/s, spots at other places | No change in this run |
| N5 | steps 4,500 U, 8,000 U and p | As N1, peaks 38.26 and 35.58 m/s; p -245 to 58 m^2/s^2 at step 8,000 | No change in this run |
| M1-inlet-speed | steps 4,500 U, 8,000 U and p | Colour bar ends at 13.62 and 11.58 m/s, far below the stated 32.2. The fastest flow is a thin jet at the bottom, y about 3 %; the upper part is slow, with dark patches and stair-step streaks along the mesh cells. p -43 to 11 m^2/s^2 | Yes, plainly: the colour-bar numbers and the shape |
| M2-viscosity | steps 4,500 U, 8,000 U and p | No spots or vortices at all: smooth layers and one thin dark line, stair-step streaks at the upper left. p is a smooth left-to-right gradient, -112 to -33 m^2/s^2, with no low-pressure cores. Peak 36.95 and 38.12 m/s, in the normal range | Yes in the pattern; not in the peak |
| M3-slip-walls | steps 4,500 U, 8,000 U and p | One long dark band at y about 20 % instead of a row of spots, and a bright layer against the bottom edge at x about 5 to 50 %, where the normal runs are dark. p shows one large low-pressure zone. Peak 36.76 and 37.15 m/s, in the normal range | Yes to a careful eye: the fast flow against the lower wall and the larger structures |
| M4-moving-wall | steps 4,500 U, 8,000 U and p | Almost the same as N5 at the same step: the same spots, moved by about 1 to 2 % of the window; peaks 38.61 and 35.66 m/s against 38.26 and 35.58 m/s | No: the moved wall is at y = 0.1143 m and the window ends at y = 0.04 m, and I could not tell this run from N5 |
| M5-half-inlet | steps 4,500 U, 8,000 U and p | The pattern of a normal run with fewer spots at step 4,500, the same kind at step 8,000. The colour bar ends at 18.93 and 18.10 m/s, about half of the normal peak and below the stated 32.2. p -60 to 25 m^2/s^2 | In the colour-bar numbers; not in the shape. The split of the inlet does not reach the window: from x = -1.651 m to the step takes at least 0.051 s at 32.2 m/s, and the run lasts 0.04 s |

Facts these pictures rest on:

- All five changes took effect (`flow-check`): the last written U holds each changed boundary
  entry, M2's `transportProperties` has nu = 0.00156 m^2/s, and the inlet flux in the last written
  phi is -0.04155 in the normal runs and M2 to M4, -0.004155 in M1 and -0.02077 in M5 (m^3/s per
  the mesh's depth).
- In 0.04 s a flow at 32.2 m/s travels 1.29 m: 10.7 window lengths, about 2 lengths of the channel
  behind the step (0.635 m), 0.56 of the domain (2.286 m). At 3.22 m/s the same time is 1.07 window
  lengths, so M1's window still holds what the start state left there. So "the flow has had time
  to respond" holds for the bulk flow, which follows the inlet at once, and for the window at the
  normal speed; M1's frames are still changing.
- The five normal runs are pieces of one trajectory (`flow/normal-overlap.json`, job 24947055). The
  solver is deterministic and the long run had reached its time step of 5e-6 s, so the 40 normal
  frames hold 24 different flow times. The 16 pairs at one flow time differ by at most 4.3e-4 m/s
  and 0.015 m^2/s^2 and by at most 163 pixels below the title. N1 at step 8,000 and N2 at step 6,000
  are such a pair. The design's example start times were kept.
