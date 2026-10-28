| model | set | mode | answered | fastest within 10 % | lowest p within 10 % | speed trend | p trend | region | fixed-answer score | median prompt tokens | median s |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gemma-4-12b-it-qat-q4_0-vision | dev-sequence-v1 | sequence | 45/45 |  |  | 14/45 | 15/45 | 29/45 | 15 / 20 / 39 | 882 | 3.4 |
| gemma-4-12b-it-qat-q4_0-vision | dev-sequence-v2own | sequence | 45/45 |  |  | 32/45 | 28/45 | 35/45 | 15 / 20 / 39 | 2213 | 4.5 |
| gemma-4-12b-it-qat-q4_0-vision | dev-sequence-v2own-t | sequence | 45/45 |  |  | 36/45 | 26/45 | 32/45 | 15 / 20 / 39 | 2333 | 4.2 |
| gemma-4-12b-it-qat-q4_0-vision | dev-sequence-v2own-tn | sequence | 45/45 |  |  | 33/45 | 28/45 | 31/45 | 15 / 20 / 39 | 2521 | 4.5 |
| gemma-4-12b-it-qat-q4_0-vision | dev-sequence-numbers | sequence | 45/45 |  |  | 32/45 | 28/45 | 39/45 | 15 / 20 / 39 | 756 | 3.0 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | dev-sequence-v1 | sequence | 45/45 |  |  | 16/45 | 19/45 | 34/45 | 15 / 20 / 39 | 882 | 2.7 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | dev-sequence-v2own | sequence | 45/45 |  |  | 31/45 | 36/45 | 31/45 | 15 / 20 / 39 | 2213 | 4.4 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | dev-sequence-v2own-t | sequence | 45/45 |  |  | 29/45 | 34/45 | 25/45 | 15 / 20 / 39 | 2333 | 4.4 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | dev-sequence-v2own-tn | sequence | 45/45 |  |  | 33/45 | 33/45 | 22/45 | 15 / 20 / 39 | 2521 | 4.5 |
| gemma-4-26B-A4B-it-qat-q4_0-vision | dev-sequence-numbers | sequence | 45/45 |  |  | 36/45 | 37/45 | 41/45 | 15 / 20 / 39 | 756 | 2.4 |
| gemma-4-31B-it-qat-q4_0-vision | dev-sequence-v1 | sequence | 45/45 |  |  | 18/45 | 20/45 | 18/45 | 15 / 20 / 39 | 882 | 7.5 |
| gemma-4-31B-it-qat-q4_0-vision | dev-sequence-v2own | sequence | 45/45 |  |  | 32/45 | 33/45 | 35/45 | 15 / 20 / 39 | 2213 | 10.6 |
| gemma-4-31B-it-qat-q4_0-vision | dev-sequence-v2own-t | sequence | 45/45 |  |  | 32/45 | 31/45 | 33/45 | 15 / 20 / 39 | 2333 | 9.7 |
| gemma-4-31B-it-qat-q4_0-vision | dev-sequence-v2own-tn | sequence | 45/45 |  |  | 37/45 | 41/45 | 27/45 | 15 / 20 / 39 | 2521 | 10.6 |
| gemma-4-31B-it-qat-q4_0-vision | dev-sequence-numbers | sequence | 45/45 |  |  | 35/45 | 42/45 | 40/45 | 15 / 20 / 39 | 756 | 6.8 |

- gemma-4-12b-it-qat-q4_0-vision dev-sequence-v2own vs dev-sequence-v2own-t: items 45, both 31, only dev-sequence-v2own 1, only dev-sequence-v2own-t 5, neither 8
- gemma-4-12b-it-qat-q4_0-vision dev-sequence-v2own-t vs dev-sequence-v2own-tn: items 45, both 30, only dev-sequence-v2own-t 6, only dev-sequence-v2own-tn 3, neither 6
- gemma-4-12b-it-qat-q4_0-vision dev-sequence-numbers vs dev-sequence-v2own-tn: items 45, both 30, only dev-sequence-numbers 2, only dev-sequence-v2own-tn 3, neither 10
- gemma-4-12b-it-qat-q4_0-vision dev-sequence-v1 vs dev-sequence-v2own-t: items 45, both 9, only dev-sequence-v1 5, only dev-sequence-v2own-t 27, neither 4
- gemma-4-26B-A4B-it-qat-q4_0-vision dev-sequence-v2own vs dev-sequence-v2own-t: items 45, both 27, only dev-sequence-v2own 4, only dev-sequence-v2own-t 2, neither 12
- gemma-4-26B-A4B-it-qat-q4_0-vision dev-sequence-v2own-t vs dev-sequence-v2own-tn: items 45, both 27, only dev-sequence-v2own-t 2, only dev-sequence-v2own-tn 6, neither 10
- gemma-4-26B-A4B-it-qat-q4_0-vision dev-sequence-numbers vs dev-sequence-v2own-tn: items 45, both 30, only dev-sequence-numbers 6, only dev-sequence-v2own-tn 3, neither 6
- gemma-4-26B-A4B-it-qat-q4_0-vision dev-sequence-v1 vs dev-sequence-v2own-t: items 45, both 12, only dev-sequence-v1 4, only dev-sequence-v2own-t 17, neither 12
- gemma-4-31B-it-qat-q4_0-vision dev-sequence-v2own vs dev-sequence-v2own-t: items 45, both 26, only dev-sequence-v2own 6, only dev-sequence-v2own-t 6, neither 7
- gemma-4-31B-it-qat-q4_0-vision dev-sequence-v2own-t vs dev-sequence-v2own-tn: items 45, both 31, only dev-sequence-v2own-t 1, only dev-sequence-v2own-tn 6, neither 7
- gemma-4-31B-it-qat-q4_0-vision dev-sequence-numbers vs dev-sequence-v2own-tn: items 45, both 35, only dev-sequence-numbers 0, only dev-sequence-v2own-tn 2, neither 8
- gemma-4-31B-it-qat-q4_0-vision dev-sequence-v1 vs dev-sequence-v2own-t: items 45, both 11, only dev-sequence-v1 7, only dev-sequence-v2own-t 21, neither 6

fixed-answer score: what one fixed answer per plotted range would get (describe: fastest / lowest p; sequence: speed / p / region). Paired lines count items right in both, one or neither set (describe: fastest flow within 10 %; sequence: speed trend).
