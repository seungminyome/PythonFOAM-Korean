# wrong-setup test 2 2026-11-03: results

One run is one sample; the primary frame is its last state (step 8000). Right: a normal run answered consistent, a wrong run inconsistent. Right for the right reason: also the cause is the run's own. The constant baseline answers consistent everywhere. p: exact McNemar test against the strongest baseline on the same frames; CI: bootstrap over pairs.

## Condition: stated

### primary frames (58)

| answers from | right | normal right | wrong right | right for right reason | 95 % CI | vs labels: only it / only this, p |
|---|---:|---:|---:|---:|---|---|
| constant | 29 | 29 | 0 |  | 0.50 to 0.50 | 17 / 1, p = 0.000145 |
| peak rule | 43 | 29 | 14 |  | 0.66 to 0.83 | 8 / 6, p = 0.791 |
| labels | 45 | 28 | 17 |  | 0.67 to 0.88 |  |
| labels + pixels | 44 | 25 | 19 |  | 0.66 to 0.86 | 5 / 4, p = 1 |
| pixels only | 44 | 25 | 19 |  | 0.64 to 0.86 | 7 / 6, p = 1 |
| gemma-4-31B-it-qat-q4_0-vision t0 | 44 | 18 | 26 | 27 | 0.67 to 0.84 | 14 / 13, p = 1 |
| gemma-4-31B-it-qat-q4_0-vision t07a | 34 | 9 | 25 | 19 | 0.48 to 0.69 | 23 / 12, p = 0.0895 |
| gemma-4-31B-it-qat-q4_0-vision t07b | 38 | 13 | 25 | 23 | 0.55 to 0.76 | 19 / 12, p = 0.281 |

By cause (wrong runs right / runs):

| answers from | inlet_profile | inlet_speed | viscosity | walls |
|---|---:|---:|---:|---:|
| constant | 0 / 6 | 0 / 8 | 0 / 8 | 0 / 7 |
| peak rule | 6 / 6 | 6 / 8 | 2 / 8 | 0 / 7 |
| labels | 4 / 6 | 4 / 8 | 2 / 8 | 7 / 7 |
| labels + pixels | 4 / 6 | 4 / 8 | 4 / 8 | 7 / 7 |
| pixels only | 3 / 6 | 4 / 8 | 5 / 8 | 7 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t0 | 6 / 6 | 8 / 8 | 8 / 8 | 4 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t07a | 6 / 6 | 8 / 8 | 8 / 8 | 3 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t07b | 6 / 6 | 8 / 8 | 7 / 8 | 4 / 7 |

### all frames (174)

| answers from | right | normal right | wrong right | right for right reason | 95 % CI | vs None: only it / only this, p |
|---|---:|---:|---:|---:|---|---|
| gemma-4-31B-it-qat-q4_0-vision t0 | 123 | 47 | 76 | 69 | 0.64 to 0.77 |  |
| gemma-4-31B-it-qat-q4_0-vision t07a | 103 | 26 | 77 | 52 | 0.53 to 0.66 |  |
| gemma-4-31B-it-qat-q4_0-vision t07b | 116 | 43 | 73 | 68 | 0.59 to 0.74 |  |

## Condition: blind

### primary frames (58)

| answers from | right | normal right | wrong right | right for right reason | 95 % CI | vs labels: only it / only this, p |
|---|---:|---:|---:|---:|---|---|
| constant | 29 | 29 | 0 |  | 0.50 to 0.50 | 17 / 1, p = 0.000145 |
| labels | 45 | 28 | 17 |  | 0.67 to 0.88 |  |
| labels + pixels | 44 | 25 | 19 |  | 0.66 to 0.86 | 5 / 4, p = 1 |
| pixels only | 44 | 25 | 19 |  | 0.64 to 0.86 | 7 / 6, p = 1 |
| gemma-4-31B-it-qat-q4_0-vision t0 | 28 | 3 | 25 | 6 | 0.40 to 0.57 | 29 / 12, p = 0.0115 |
| gemma-4-31B-it-qat-q4_0-vision t07a | 31 | 5 | 26 | 10 | 0.45 to 0.64 | 26 / 12, p = 0.0336 |
| gemma-4-31B-it-qat-q4_0-vision t07b | 28 | 1 | 27 | 1 | 0.43 to 0.53 | 29 / 12, p = 0.0115 |

By cause (wrong runs right / runs):

| answers from | inlet_profile | inlet_speed | viscosity | walls |
|---|---:|---:|---:|---:|
| constant | 0 / 6 | 0 / 8 | 0 / 8 | 0 / 7 |
| labels | 4 / 6 | 4 / 8 | 2 / 8 | 7 / 7 |
| labels + pixels | 4 / 6 | 4 / 8 | 4 / 8 | 7 / 7 |
| pixels only | 3 / 6 | 4 / 8 | 5 / 8 | 7 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t0 | 4 / 6 | 7 / 8 | 8 / 8 | 6 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t07a | 4 / 6 | 8 / 8 | 8 / 8 | 6 / 7 |
| gemma-4-31B-it-qat-q4_0-vision t07b | 5 / 6 | 8 / 8 | 8 / 8 | 6 / 7 |

### all frames (174)

| answers from | right | normal right | wrong right | right for right reason | 95 % CI | vs None: only it / only this, p |
|---|---:|---:|---:|---:|---|---|
| gemma-4-31B-it-qat-q4_0-vision t0 | 85 | 3 | 82 | 13 | 0.45 to 0.52 |  |
| gemma-4-31B-it-qat-q4_0-vision t07a | 88 | 7 | 81 | 15 | 0.46 to 0.55 |  |
| gemma-4-31B-it-qat-q4_0-vision t07b | 84 | 1 | 83 | 4 | 0.45 to 0.51 |  |
