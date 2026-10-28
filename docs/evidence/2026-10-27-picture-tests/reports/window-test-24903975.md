| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5-35b-a3b-q8_0-vision | dev-sequence-v1 | sequence | 45/45 |  |  | 15/45 | 18/45 | 25/45 | 15 / 20 / 39 | 1206 | 1.6 |
| qwen3.5-35b-a3b-q8_0-vision | dev-sequence-v2own | sequence | 45/45 |  |  | 31/45 | 32/45 | 33/45 | 15 / 20 / 39 | 2185 | 2.1 |
| qwen3.5-35b-a3b-q8_0-vision | dev-sequence-v2own-t | sequence | 45/45 |  |  | 34/45 | 35/45 | 31/45 | 15 / 20 / 39 | 2296 | 2.0 |
| qwen3.5-35b-a3b-q8_0-vision | dev-sequence-v2own-tn | sequence | 45/45 |  |  | 32/45 | 28/45 | 32/45 | 15 / 20 / 39 | 2447 | 1.9 |
| qwen3.5-35b-a3b-q8_0-vision | dev-sequence-numbers | sequence | 45/45 |  |  | 34/45 | 33/45 | 39/45 | 15 / 20 / 39 | 683 | 1.3 |

- qwen3.5-35b-a3b-q8_0-vision dev-sequence-v2own vs dev-sequence-v2own-t: items 45, both 29, only dev-sequence-v2own 2, only dev-sequence-v2own-t 5, neither 9
- qwen3.5-35b-a3b-q8_0-vision dev-sequence-v2own-t vs dev-sequence-v2own-tn: items 45, both 29, only dev-sequence-v2own-t 5, only dev-sequence-v2own-tn 3, neither 8
- qwen3.5-35b-a3b-q8_0-vision dev-sequence-numbers vs dev-sequence-v2own-tn: items 45, both 30, only dev-sequence-numbers 4, only dev-sequence-v2own-tn 2, neither 9
- qwen3.5-35b-a3b-q8_0-vision dev-sequence-v1 vs dev-sequence-v2own-t: items 45, both 14, only dev-sequence-v1 1, only dev-sequence-v2own-t 20, neither 10

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
