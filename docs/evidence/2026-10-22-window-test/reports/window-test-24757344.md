| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-E2B-it-Q4_0-vision | flow-window-v1 | describe | 48/48 | 6/48 | 7/48 |  |  |  | 7 / 7 | 571 | 1.0 |
| gemma-4-E2B-it-Q4_0-vision | flow-window-v2 | describe | 48/48 | 5/48 | 14/48 |  |  |  | 7 / 7 | 1047 | 1.0 |
| gemma-4-E2B-it-Q4_0-bf16proj-vision | flow-window-v1 | describe | 48/48 | 5/48 | 5/48 |  |  |  | 7 / 7 | 571 | 1.0 |
| gemma-4-E2B-it-Q4_0-bf16proj-vision | flow-window-v2 | describe | 48/48 | 5/48 | 13/48 |  |  |  | 7 / 7 | 1047 | 1.1 |
| gemma-4-E2B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 5/48 | 5/48 |  |  |  | 7 / 7 | 571 | 0.9 |
| gemma-4-E2B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 3/48 | 8/48 |  |  |  | 7 / 7 | 1047 | 1.0 |
| gemma-4-E4B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 8/48 | 5/48 |  |  |  | 7 / 7 | 571 | 1.2 |
| gemma-4-E4B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 16/48 | 13/48 |  |  |  | 7 / 7 | 1047 | 1.4 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 10/48 | 17/48 |  |  |  | 7 / 7 | 575 | 2.9 |
| gemma-4-12b-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 46/48 | 47/48 |  |  |  | 7 / 7 | 1051 | 3.2 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 3/48 | 6/48 |  |  |  | 7 / 7 | 575 | 1.9 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 47/48 | 47/48 |  |  |  | 7 / 7 | 1051 | 2.4 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v1 | describe | 48/48 | 13/48 | 15/48 |  |  |  | 7 / 7 | 575 | 6.2 |
| gemma-4-31B-it-qat-q4_0-vision | flow-window-v2 | describe | 48/48 | 45/48 | 48/48 |  |  |  | 7 / 7 | 1051 | 7.5 |
| qwen3-vl-8b-instruct-q8_0-vision | flow-window-v1 | describe | 48/48 | 3/48 | 4/48 |  |  |  | 7 / 7 | 662 | 2.2 |
| qwen3-vl-8b-instruct-q8_0-vision | flow-window-v2 | describe | 48/48 | 21/48 | 36/48 |  |  |  | 7 / 7 | 1021 | 2.4 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v1 | describe | 48/48 | 0/48 | 2/48 |  |  |  | 7 / 7 | 662 | 10.9 |
| qwen3-vl-32b-instruct-q8_0-vision | flow-window-v2 | describe | 48/48 | 38/48 | 39/48 |  |  |  | 7 / 7 | 1021 | 11.0 |
| qwen3.5-27b-q8_0-vision | flow-window-v1 | describe | 48/48 | 2/48 | 3/48 |  |  |  | 7 / 7 | 666 | 8.0 |
| qwen3.5-27b-q8_0-vision | flow-window-v2 | describe | 48/48 | 43/48 | 46/48 |  |  |  | 7 / 7 | 1026 | 8.5 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v1 | describe | 48/48 | 5/48 | 3/48 |  |  |  | 7 / 7 | 666 | 2.3 |
| qwen3.5-35b-a3b-q8_0-vision | flow-window-v2 | describe | 48/48 | 47/48 | 46/48 |  |  |  | 7 / 7 | 1026 | 2.3 |

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
