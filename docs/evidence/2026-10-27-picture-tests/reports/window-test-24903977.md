| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-vl-32b-instruct-q4_k_m-vision | flow-window-v1 | describe | 140/140 | 0/140 | 7/140 |  |  |  | 16 / 17 | 1519 | 6.9 |
| qwen3-vl-32b-instruct-q4_k_m-vision | flow-window-v2 | describe | 140/140 | 112/140 | 134/140 |  |  |  | 16 / 17 | 2583 | 7.6 |
| qwen3.5-27b-q4_k_m-vision | flow-window-v1 | describe | 140/140 | 15/140 | 25/140 |  |  |  | 16 / 17 | 1523 | 5.5 |
| qwen3.5-27b-q4_k_m-vision | flow-window-v2 | describe | 140/140 | 128/140 | 136/140 |  |  |  | 16 / 17 | 2588 | 6.1 |
| qwen3.5-35b-a3b-q4_k_m-vision | flow-window-v1 | describe | 140/140 | 7/140 | 3/140 |  |  |  | 16 / 17 | 1523 | 1.9 |
| qwen3.5-35b-a3b-q4_k_m-vision | flow-window-v2 | describe | 140/140 | 133/140 | 137/140 |  |  |  | 16 / 17 | 2588 | 2.0 |

fixed-answer score: what one fixed answer per plotted range would get; flow-window-v1, flow-window-v2: one fixed answer for the whole set (every request has its own window) (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
