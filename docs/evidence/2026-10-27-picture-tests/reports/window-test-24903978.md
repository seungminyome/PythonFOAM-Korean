| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v1 | describe | 40/40 | 10/40 | 1/40 |  |  |  | 8 / 8 | 568 | 3.6 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v2 | describe | 40/40 | 32/40 | 18/40 |  |  |  | 8 / 8 | 1044 | 4.2 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v1 | describe | 40/40 | 9/40 | 3/40 |  |  |  | 8 / 8 | 568 | 2.8 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v2 | describe | 40/40 | 39/40 | 26/40 |  |  |  | 8 / 8 | 1044 | 3.6 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v1 | describe | 40/40 | 3/40 | 7/40 |  |  |  | 8 / 8 | 568 | 7.1 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v2 | describe | 40/40 | 35/40 | 38/40 |  |  |  | 8 / 8 | 1044 | 9.2 |

fixed-answer score: what one fixed answer per plotted range would get; flow-window-v1, flow-window-v2: one fixed answer for the whole set (every request has its own window) (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
