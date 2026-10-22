| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v1 | describe | 140/140 | 12/140 | 30/140 |  |  |  | 16 / 17 | 576 | 2.8 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v2 | describe | 140/140 | 108/140 | 130/140 |  |  |  | 16 / 17 | 1052 | 3.1 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v1 | describe | 140/140 | 19/140 | 22/140 |  |  |  | 16 / 17 | 576 | 1.9 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v2 | describe | 140/140 | 113/140 | 139/140 |  |  |  | 16 / 17 | 1052 | 2.4 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v1 | describe | 140/140 | 17/140 | 25/140 |  |  |  | 16 / 17 | 576 | 5.7 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v2 | describe | 140/140 | 106/140 | 133/140 |  |  |  | 16 / 17 | 1052 | 7.3 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v1 | describe | 140/140 | 8/140 | 11/140 |  |  |  | 16 / 17 | 668 | 2.0 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v2 | describe | 140/140 | 121/140 | 134/140 |  |  |  | 16 / 17 | 1028 | 2.1 |
| qwen3.5-27b-q8_0-vision | flow-window-v1 | describe | 140/140 | 10/140 | 19/140 |  |  |  | 16 / 17 | 668 | 8.2 |
| qwen3.5-27b-q8_0-vision | flow-window-v2 | describe | 140/140 | 109/140 | 136/140 |  |  |  | 16 / 17 | 1028 | 8.5 |
| gemma-4-E4B-it-qat-q4_0-vision | flow-window-v1 | describe | 140/140 | 16/140 | 21/140 |  |  |  | 16 / 17 | 572 | 1.2 |
| gemma-4-E4B-it-qat-q4_0-vision | flow-window-v2 | describe | 140/140 | 39/140 | 34/140 |  |  |  | 16 / 17 | 1048 | 1.4 |

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
