Scored items: 80 frames, 40 normal and 40 wrong. A frame is right when a normal frame is answered consistent or a wrong frame inconsistent; cannot_tell and no answer are wrong on both. The constant baseline gets 40 of 80.

| answers from | answered | right of 80 | normal said consistent | normal said inconsistent | normal cannot_tell | wrong said inconsistent | wrong said consistent | wrong cannot_tell |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3.5-35b-a3b-q8_0-vision | 80 | 45 | 40 of 40 | 0 | 0 | 5 of 40 | 35 | 0 |
| Rule: peak \|U\| in the window between 1 and 2 times 32.2 m/s | 80 | 56 | 40 of 40 | 0 | 0 | 16 of 40 | 24 | 0 |
| Constant baseline | | 40 | | | | | | |

Right of the frames of each run.

| run | class | change | qwen3.5-35b-a3b-q8_0-vision | peak \|U\| rule |
|---|---|---|---:|---:|
| N1 | normal | none; start state t = 0.06 s of the developed flow | 8 of 8 | 8 of 8 |
| N2 | normal | none; start state t = 0.07 s of the developed flow | 8 of 8 | 8 of 8 |
| N3 | normal | none; start state t = 0.08 s of the developed flow | 8 of 8 | 8 of 8 |
| N4 | normal | none; start state t = 0.09 s of the developed flow | 8 of 8 | 8 of 8 |
| N5 | normal | none; start state t = 0.1 s of the developed flow | 8 of 8 | 8 of 8 |
| M1-inlet-speed | wrong | inlet velocity 3.22 m/s instead of 32.2 m/s | 0 of 8 | 8 of 8 |
| M2-viscosity | wrong | nu 1.56e-3 m^2/s instead of 1.56e-5 m^2/s | 5 of 8 | 0 of 8 |
| M3-slip-walls | wrong | lowerWall and upperWall slip instead of noSlip | 0 of 8 | 0 of 8 |
| M4-moving-wall | wrong | upperWall fixedValue (-32.2 0 0) instead of noSlip | 0 of 8 | 0 of 8 |
| M5-half-inlet | wrong | lower half of the inlet at velocity 0, upper half at 32.2 m/s | 0 of 8 | 8 of 8 |

Numbers at the frames, from the arrays and the log block of each frame's step: the range over the normal frames, each wrong run's range, and in brackets how many of its frames lie outside the normal range.

| number | normal frames | M1-inlet-speed | M2-viscosity | M3-slip-walls | M4-moving-wall | M5-half-inlet |
|---|---|---|---|---|---|---|
| largest Courant number | 0.2312 to 0.3367 | 0.2692 to 0.3573 (3) | 0.2158 to 0.2257 (8) | 0.7158 to 1.3 (8) | 0.2488 to 0.3432 (1) | 0.1256 to 0.208 (8) |
| mean Courant number | 0.01698 to 0.01714 | 0.002692 to 0.002749 (8) | 0.01687 (8) | 0.01714 to 0.01719 (8) | 0.01717 to 0.01732 (8) | 0.008752 to 0.008802 (8) |
| Ux initial residual | 6.357e-06 to 1.203e-05 | 9.58e-06 to 1.378e-05 (2) | 5.493e-06 to 1.152e-05 (2) | 4.455e-06 to 4.861e-06 (8) | 6.953e-06 to 1.084e-05 (0) | 2.544e-05 to 3.63e-05 (8) |
| Uy initial residual | 0.0001687 to 0.000436 | 7.342e-05 to 0.0001603 (8) | 1.428e-05 to 2.227e-05 (8) | 2.377e-05 to 4.098e-05 (8) | 0.0002111 to 0.0004049 (0) | 0.0001456 to 0.0002012 (5) |
| p initial residual, first solve | 0.009193 to 0.03345 | 0.002529 to 0.006147 (8) | 0.01809 to 0.02304 (0) | 0.003643 to 0.006371 (8) | 0.01048 to 0.03046 (0) | 0.002666 to 0.004239 (8) |
| Ux final residual | 1.923e-08 to 9.945e-06 | 6.489e-10 to 9.926e-06 (4) | 1.568e-08 to 9.216e-06 (2) | 4.455e-06 to 4.861e-06 (0) | 2.087e-08 to 9.613e-06 (0) | 1.39e-09 to 4.147e-09 (8) |
| Uy final residual | 2.632e-07 to 1.043e-06 | 6.596e-09 to 8.816e-09 (8) | 7.772e-08 to 1.498e-07 (8) | 1.95e-08 to 8.081e-08 (8) | 3.197e-07 to 9.631e-07 (0) | 1.708e-08 to 1.021e-07 (8) |
| p final residual, last solve | 3.297e-07 to 9.998e-07 | 6.57e-07 to 9.736e-07 (0) | 6.953e-07 to 9.181e-07 (0) | 7.79e-07 to 9.847e-07 (0) | 4.062e-07 to 9.648e-07 (0) | 5.648e-07 to 9.41e-07 (0) |
| continuity error, sum local | 4.271e-13 to 1.167e-12 | 1.196e-13 to 1.906e-13 (8) | 1.22e-13 to 1.663e-13 (8) | 4.914e-13 to 6.369e-13 (0) | 6.15e-13 to 1.241e-12 (2) | 2.563e-13 to 4.325e-13 (7) |
| continuity error, global (absolute) | 1.369e-14 to 1.653e-13 | 7.86e-15 to 2.112e-14 (5) | 1.578e-16 to 2.924e-14 (4) | 3.56e-14 to 8.004e-14 (0) | 2.965e-14 to 1.151e-13 (0) | 1.427e-14 to 5.793e-14 (0) |
| continuity error, cumulative (absolute) | 2.041e-09 to 7.244e-09 | 9.172e-09 to 9.899e-09 (8) | 1.12e-08 to 2.485e-08 (8) | 2.302e-09 to 3.627e-09 (0) | 1.519e-10 to 2.434e-09 (6) | 8.106e-09 to 8.226e-09 (8) |
| peak \|U\| in the window (m/s) | 34.73 to 39.44 | 11.58 to 13.62 (8) | 36.95 to 38.12 (0) | 36.69 to 37.3 (0) | 35.62 to 39.51 (1) | 18.1 to 19.7 (8) |
| lowest p in the window (m^2/s^2) | -465.6 to -215.6 | -69.59 to -43.01 (8) | -112.1 to -98.08 (8) | -330 to -293.2 (0) | -464.1 to -248.8 (0) | -111.5 to -60.4 (8) |

Numbers per run from the logs: the range over the normal runs and each wrong run's value, marked \* when outside that range.

| number | normal runs | M1-inlet-speed | M2-viscosity | M3-slip-walls | M4-moving-wall | M5-half-inlet |
|---|---|---|---|---|---|---|
| largest Courant number, whole run | 0.3414 to 0.3467 | 10.69 \* | 0.2836 \* | 1.309 \* | 0.3479 \* | 5.488 \* |
| largest Courant number, from the first frame on | 0.3414 to 0.3467 | 0.3586 \* | 0.2257 \* | 1.309 \* | 0.3468 \* | 0.2086 \* |
| mean Courant number, from the first frame on | 0.01707 to 0.01709 | 0.002715 \* | 0.01687 \* | 0.01718 \* | 0.01724 \* | 0.008769 \* |
| Ux initial residual, last step | 8.673e-06 to 1.203e-05 | 9.694e-06 | 5.493e-06 \* | 4.652e-06 \* | 9.133e-06 | 2.544e-05 \* |
| Uy initial residual, last step | 0.0002232 to 0.000436 | 7.342e-05 \* | 1.428e-05 \* | 2.377e-05 \* | 0.0003374 | 0.0001466 \* |
| p initial residual, first solve of the last step | 0.01025 to 0.02998 | 0.006147 \* | 0.02304 | 0.003643 \* | 0.02743 | 0.004149 \* |
| Ux final residual, last step | 2.16e-08 to 9.843e-06 | 9.694e-06 | 5.493e-06 | 4.652e-06 | 9.133e-06 | 2.183e-09 \* |
| Uy final residual, last step | 3.895e-07 to 1.043e-06 | 7.638e-09 \* | 1.498e-07 \* | 1.95e-08 \* | 5.103e-07 | 4.255e-08 \* |
| p final residual, last solve of the last step | 6.902e-07 to 9.543e-07 | 8.51e-07 | 9.181e-07 | 9.118e-07 | 8.809e-07 | 5.648e-07 \* |
| continuity error, sum local, last step | 6.718e-13 to 1.167e-12 | 1.789e-13 \* | 1.663e-13 \* | 5.727e-13 \* | 9.398e-13 | 2.563e-13 \* |
| continuity error, global (absolute), last step | 1.455e-14 to 1.653e-13 | 1.866e-14 | 2.151e-14 | 4.256e-14 | 9.402e-14 | 1.427e-14 \* |
| continuity error, cumulative (absolute), last step | 4.348e-09 to 7.237e-09 | 9.899e-09 \* | 2.485e-08 \* | 3.425e-09 \* | 2.434e-09 \* | 8.226e-09 \* |

Leak check: 80 requests; apart from the pictures and the frame's own step and time the bodies are byte-identical; 8 distinct texts; the most any rule on the request text can get is 40 of 80, the constant baseline 40; problems: 0.

| answers from | median prompt tokens, normal / wrong | median s per request |
|---|---:|---:|
| qwen3.5-35b-a3b-q8_0-vision | 970.5 / 970.5 | 0.92 |

Every frame: the peak |U| and lowest p in the window, the rule's answer and each model's (c consistent, i inconsistent, ? cannot_tell, - no answer).

| frame | class | peak \|U\| | lowest p | rule | qwen3.5-35b-a3b-q8_0-vision |
|---|---|---:|---:|---|---|
| N1-step04500 | normal | 39.22 | -383.6 | c | c |
| N1-step05000 | normal | 37.91 | -376.1 | c | c |
| N1-step05500 | normal | 38.27 | -327.3 | c | c |
| N1-step06000 | normal | 37.86 | -364.9 | c | c |
| N1-step06500 | normal | 36.6 | -262.7 | c | c |
| N1-step07000 | normal | 37.36 | -371.3 | c | c |
| N1-step07500 | normal | 35.07 | -230.1 | c | c |
| N1-step08000 | normal | 37.02 | -362.4 | c | c |
| N2-step04500 | normal | 36.6 | -262.7 | c | c |
| N2-step05000 | normal | 37.36 | -371.3 | c | c |
| N2-step05500 | normal | 35.07 | -230.1 | c | c |
| N2-step06000 | normal | 37.02 | -362.4 | c | c |
| N2-step06500 | normal | 34.9 | -226.1 | c | c |
| N2-step07000 | normal | 39.34 | -465.6 | c | c |
| N2-step07500 | normal | 35.53 | -251.4 | c | c |
| N2-step08000 | normal | 38.52 | -446.1 | c | c |
| N3-step04500 | normal | 34.9 | -226.1 | c | c |
| N3-step05000 | normal | 39.34 | -465.6 | c | c |
| N3-step05500 | normal | 35.53 | -251.4 | c | c |
| N3-step06000 | normal | 38.52 | -446.1 | c | c |
| N3-step06500 | normal | 38.06 | -362.3 | c | c |
| N3-step07000 | normal | 38.56 | -365.2 | c | c |
| N3-step07500 | normal | 37.48 | -361.2 | c | c |
| N3-step08000 | normal | 39.44 | -420.6 | c | c |
| N4-step04500 | normal | 38.06 | -362.3 | c | c |
| N4-step05000 | normal | 38.56 | -365.2 | c | c |
| N4-step05500 | normal | 37.48 | -361.2 | c | c |
| N4-step06000 | normal | 39.44 | -420.6 | c | c |
| N4-step06500 | normal | 38.26 | -373.6 | c | c |
| N4-step07000 | normal | 38.6 | -356.3 | c | c |
| N4-step07500 | normal | 37.75 | -358.5 | c | c |
| N4-step08000 | normal | 36.35 | -253.7 | c | c |
| N5-step04500 | normal | 38.26 | -373.6 | c | c |
| N5-step05000 | normal | 38.6 | -356.3 | c | c |
| N5-step05500 | normal | 37.75 | -358.5 | c | c |
| N5-step06000 | normal | 36.35 | -253.7 | c | c |
| N5-step06500 | normal | 36.63 | -324.6 | c | c |
| N5-step07000 | normal | 34.73 | -215.6 | c | c |
| N5-step07500 | normal | 39.12 | -459.1 | c | c |
| N5-step08000 | normal | 35.58 | -245.4 | c | c |
| M1-inlet-speed-step04500 | wrong | 13.62 | -69.59 | i | c |
| M1-inlet-speed-step05000 | wrong | 13.24 | -63.92 | i | c |
| M1-inlet-speed-step05500 | wrong | 12.84 | -58.49 | i | c |
| M1-inlet-speed-step06000 | wrong | 12.47 | -53.63 | i | c |
| M1-inlet-speed-step06500 | wrong | 12.19 | -49.58 | i | c |
| M1-inlet-speed-step07000 | wrong | 11.93 | -46.55 | i | c |
| M1-inlet-speed-step07500 | wrong | 11.74 | -44.52 | i | c |
| M1-inlet-speed-step08000 | wrong | 11.58 | -43.01 | i | c |
| M2-viscosity-step04500 | wrong | 36.95 | -98.08 | c | c |
| M2-viscosity-step05000 | wrong | 37.15 | -100.5 | c | c |
| M2-viscosity-step05500 | wrong | 37.33 | -102.9 | c | c |
| M2-viscosity-step06000 | wrong | 37.51 | -105 | c | i |
| M2-viscosity-step06500 | wrong | 37.67 | -107 | c | i |
| M2-viscosity-step07000 | wrong | 37.83 | -108.8 | c | i |
| M2-viscosity-step07500 | wrong | 37.98 | -110.5 | c | i |
| M2-viscosity-step08000 | wrong | 38.12 | -112.1 | c | i |
| M3-slip-walls-step04500 | wrong | 36.76 | -330 | c | c |
| M3-slip-walls-step05000 | wrong | 36.69 | -293.2 | c | c |
| M3-slip-walls-step05500 | wrong | 37.09 | -310.5 | c | c |
| M3-slip-walls-step06000 | wrong | 37.3 | -301.4 | c | c |
| M3-slip-walls-step06500 | wrong | 37.21 | -324.1 | c | c |
| M3-slip-walls-step07000 | wrong | 36.97 | -311.8 | c | c |
| M3-slip-walls-step07500 | wrong | 37.23 | -308.3 | c | c |
| M3-slip-walls-step08000 | wrong | 37.15 | -305.6 | c | c |
| M4-moving-wall-step04500 | wrong | 38.61 | -386.9 | c | c |
| M4-moving-wall-step05000 | wrong | 39.4 | -398.7 | c | c |
| M4-moving-wall-step05500 | wrong | 38.39 | -393.4 | c | c |
| M4-moving-wall-step06000 | wrong | 37.8 | -307.9 | c | c |
| M4-moving-wall-step06500 | wrong | 37.12 | -329 | c | c |
| M4-moving-wall-step07000 | wrong | 35.62 | -248.8 | c | c |
| M4-moving-wall-step07500 | wrong | 39.51 | -464.1 | c | c |
| M4-moving-wall-step08000 | wrong | 35.66 | -254.5 | c | c |
| M5-half-inlet-step04500 | wrong | 18.93 | -83.95 | i | c |
| M5-half-inlet-step05000 | wrong | 18.74 | -81.4 | i | c |
| M5-half-inlet-step05500 | wrong | 18.65 | -81.03 | i | c |
| M5-half-inlet-step06000 | wrong | 18.46 | -75.31 | i | c |
| M5-half-inlet-step06500 | wrong | 19.46 | -85.21 | i | c |
| M5-half-inlet-step07000 | wrong | 19.7 | -111.5 | i | c |
| M5-half-inlet-step07500 | wrong | 18.12 | -78.1 | i | c |
| M5-half-inlet-step08000 | wrong | 18.1 | -60.4 | i | c |
