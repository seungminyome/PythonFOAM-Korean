| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 13/48 | 12/48 |  |  |  | 9 / 9 | 575 | 3.1 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 48/48 | 48/48 |  |  |  | 9 / 9 | 1051 | 3.4 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 4/48 | 5/48 |  |  |  | 9 / 9 | 575 | 1.9 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 48/48 | 48/48 |  |  |  | 9 / 9 | 1051 | 2.4 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 7/48 | 8/48 |  |  |  | 9 / 9 | 575 | 5.8 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 46/48 | 48/48 |  |  |  | 9 / 9 | 1051 | 7.1 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v1 | describe | 48/48 | 0/48 | 1/48 |  |  |  | 9 / 9 | 662 | 10.8 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v2 | describe | 48/48 | 34/48 | 41/48 |  |  |  | 9 / 9 | 1021 | 11.4 |
| qwen3.5-27b-q8_0-vision | flow-window-v1 | describe | 48/48 | 3/48 | 2/48 |  |  |  | 9 / 9 | 666 | 8.2 |
| qwen3.5-27b-q8_0-vision | flow-window-v2 | describe | 48/48 | 44/48 | 48/48 |  |  |  | 9 / 9 | 1026 | 8.2 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v1 | describe | 48/48 | 5/48 | 4/48 |  |  |  | 9 / 9 | 666 | 2.2 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v2 | describe | 48/48 | 48/48 | 48/48 |  |  |  | 9 / 9 | 1026 | 2.2 |

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
