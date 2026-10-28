| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-vl-32b-instruct-q4_k_m-vision | flow-window-v1 | describe | 48/48 | 1/48 | 0/48 |  |  |  | 7 / 7 | 1517 | 6.6 |
| qwen3-vl-32b-instruct-q4_k_m-vision | flow-window-v2 | describe | 48/48 | 38/48 | 46/48 |  |  |  | 7 / 7 | 2581 | 7.8 |
| qwen3.5-27b-q4_k_m-vision | flow-window-v1 | describe | 48/48 | 2/48 | 2/48 |  |  |  | 7 / 7 | 1521 | 5.9 |
| qwen3.5-27b-q4_k_m-vision | flow-window-v2 | describe | 48/48 | 48/48 | 48/48 |  |  |  | 7 / 7 | 2586 | 6.7 |
| qwen3.5-35b-a3b-q4_k_m-vision | flow-window-v1 | describe | 48/48 | 3/48 | 4/48 |  |  |  | 7 / 7 | 1521 | 2.0 |
| qwen3.5-35b-a3b-q4_k_m-vision | flow-window-v2 | describe | 48/48 | 48/48 | 46/48 |  |  |  | 7 / 7 | 2586 | 2.2 |

fixed-answer score: what one fixed answer per plotted range would get; flow-window-v1, flow-window-v2: one fixed answer for the whole set (every request has its own window) (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
