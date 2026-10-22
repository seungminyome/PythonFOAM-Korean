| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 10/48 | 17/48 |  |  |  | 7 / 7 | 575 | 3.0 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 46/48 | 47/48 |  |  |  | 7 / 7 | 1051 | 3.5 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 3/48 | 6/48 |  |  |  | 7 / 7 | 575 | 1.9 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 46/48 | 47/48 |  |  |  | 7 / 7 | 1051 | 2.4 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 13/48 | 15/48 |  |  |  | 7 / 7 | 575 | 5.7 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 46/48 | 48/48 |  |  |  | 7 / 7 | 1051 | 7.1 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v1 | describe | 48/48 | 0/48 | 2/48 |  |  |  | 7 / 7 | 662 | 10.8 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v2 | describe | 48/48 | 36/48 | 46/48 |  |  |  | 7 / 7 | 1669 | 12.7 |
| qwen3.5-27b-q8_0-vision | flow-window-v1 | describe | 48/48 | 2/48 | 3/48 |  |  |  | 7 / 7 | 666 | 8.0 |
| qwen3.5-27b-q8_0-vision | flow-window-v2 | describe | 48/48 | 47/48 | 48/48 |  |  |  | 7 / 7 | 1674 | 9.6 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v1 | describe | 48/48 | 5/48 | 3/48 |  |  |  | 7 / 7 | 666 | 2.2 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v2 | describe | 48/48 | 48/48 | 48/48 |  |  |  | 7 / 7 | 1674 | 2.6 |

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
