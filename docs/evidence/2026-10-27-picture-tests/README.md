# 10월 27일 근거: 변화 읽기 시험, 4비트 Qwen, 원기둥 흐름

MedicineBow(와이오밍 대학교)의 Slurm 작업 다섯 개, 작업마다 GPU 한 장, 2026-10-27 12:44\~16:10 MDT, 그리고
그중 한 작업이 쓴 상태를 만든 원기둥 흐름 계산입니다. 이 작업들에서는 솔버를 돌리지 않았습니다. 같은 날의
솔버 실행은 [2026-10-27-solver](../2026-10-27-solver/README.md)에 있습니다.

[보고서](../../results-20261027.md) ·
[묶음을 만들고 돌리는 법](../../../Solver_Examples/PODFoam/llm_demo/README.md#발달한-흐름의-변화-읽기-시험-sequence_testpy) ·
[모든 압축 파일이 있는 릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/tests-2026-10-27) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-27-picture-tests/README.md)

## 작업

| 작업 | 요청 | 모델 | GPU(노드) | 시각(MDT) |
|---|---|---|---|---|
| 24903974 | `developed-sequence`: 발달한 흐름의 세 시각 묶음 45개를 다섯 가지로(225개) | 12B, 26B-A4B, 31B(Gemma 4 QAT) | NVIDIA A30(mba30-005) | 12:44\~13:48 |
| 24903975 | 같은 225개 | Qwen3.5-35B-A3B Q8_0 | NVIDIA L40S(mbl40s-007) | 14:55\~15:03 |
| 24903976 | 10월 22일의 `seed1`(96개: v1 48, v2 48), 이미지 토큰 한도와 최솟값 1024, 문맥 8192 | Qwen3-VL-32B, Qwen3.5-27B, Qwen3.5-35B-A3B, 모두 Q4_K_M | NVIDIA L40S(mbl40s-001) | 14:58\~15:26 |
| 24903977 | 10월 22일의 `developed`(280개: v1 140, v2 140), 같은 설정 | 같은 세 모델 | NVIDIA L40S(mbl40s-002) | 14:58\~16:10 |
| 24903978 | `cylinder`: 원기둥 흐름의 상태 10개, 상태마다 무작위 창 4개, v1과 v2(80개) | 12B, 26B-A4B, 31B | NVIDIA A30(mba30-005) | 13:02\~13:24 |
| 24903081, 24903218 | `pimpleFoam`, 원기둥 흐름(칸 1,800개와 7,200개), t = 0\~150 s | (CPU) | | 08:28\~08:53 |
| 24903180, 24903356 | 두 원기둥 격자에서 콜백을 켠 PODFoam: 프레임이 그려짐 | (CPU) | | 08:38\~08:55 |

`developed-sequence`의 묶음 다섯 개(묶음마다 세 시각 묶음 하나씩 같은 것):

| 묶음 | 그림 | 프롬프트 |
|---|---|---|
| `dev-sequence-v1` | 솔버의 두 칸 그림(`pod_image.py`), 시각마다 한 장 | 10월 20일 sequence 프롬프트 |
| `dev-sequence-v2own` | 필드와 시각마다 한 장, 그림마다 제 색 범위 | 10월 22일 프롬프트: 색 막대의 숫자를 비교하라 |
| `dev-sequence-v2own-t` | 같음 | 여기에 정답의 기준(증감 단어는 2 %, 자리는 5 %) |
| `dev-sequence-v2own-tn` | 같음 | 여기에 시각마다 가장 큰 \|U\|와 가장 낮은 p를 메모에 |
| `dev-sequence-numbers` | 없음 | 숫자와 기준만 |

세 시각 묶음 45개는 10월 22일 발달한 흐름(작업 24757429. 시간 간격을 스스로 맞추며 돌았고, 상태 이름은
5×10⁻⁷ s 걸음으로 센 명목상의 걸음 수: t = 0.032 s부터 0.1 s까지 1 ms마다, 간격 1, 2, 3 ms)의 상태로 만든 후보
195개에서 (시드 20261027로) 골랐고, 속력과 압력 증감의 조합 아홉
가지가 흐름이 허락하는 만큼 고르게 차도록 했습니다. 묶음마다 창은 하나이고, 모든 프레임의 가장 빠른 칸이
각 가장자리에서 폭의 15 % 이상 떨어지도록 무작위로 놓았습니다. 정답 단어: 속력은 증가 15, 감소 15, 거의 그대로
15; 압력은 더 음수 20, 덜 음수 18, 거의 그대로 7; 자리는 움직임 39, 같은 자리 6. 최고 속력이 2 % 이상 바뀐
묶음은 30개, 가장 낮은 압력이 2 % 이상 바뀐 묶음은 38개입니다.

원기둥 흐름은 OpenFOAM-9 튜토리얼의 `offsetCylinder` 경우(`pimpleFoam`, 층류)를, 원래 격자(칸 1,800개)와
방향마다 칸을 두 배로 한 격자(7,200개)에서 돌린 것입니다. 묶음은 고운 격자 실행을 t = 100 s부터 145 s까지
5 s마다 쓰고(흐름은 정상 상태: 상태 열 개의 |U|가 서로 최대 6×10⁻⁵ m/s만 다름), 창은 가장 빠른 칸 둘레에
무작위로 놓았습니다(y 폭 0.8\~2.5 m, 아래 벽 밖까지 닿을 수 있음: 흰색, 칸 없음). 상태 열 개 모두에서 가장 빠른 곳과 가장 낮은 압력은 원기둥 옆의 같은 두 칸입니다(다시 세기의
`cylinder_extreme_cells`). 이 묶음은 바뀌는 흐름이 아니라 다른 모양을 시험합니다.

## 파일

| 경로 | 내용 |
|---|---|
| `reports/<작업>.md` | 작업이 직접 쓴 보고서(`window_test.py report` 또는 `sequence_test.py report`) |
| `results/<작업>/<모델>/run.json` | 모델 이름, 서버 설명(저장소, 리비전, 파일, 설정), 묶음, 시험 묶음 manifest와 정답의 해시 |
| `results/<작업>/<모델>/<묶음>/metrics.jsonl`, `summary.json` | 요청마다 한 줄: 해석한 답과 점수, 요청 해시, 토큰, 서버 시간, 벽시계 시간; 실행기의 요약 |
| `test-sets/developed-sequence/`, `test-sets/cylinder/` | 새 묶음 두 개의 manifest(요청 해시, 만든 인자, 창 규칙, 코드 해시)와 정답. `seed1`과 `developed`의 정답은 [../2026-10-22-window-test/test-sets/](../2026-10-22-window-test/test-sets/)에 있음 |
| [pictures/](pictures/) | 요청 본문에서 풀어낸, 보낸 그대로의 그림(아래 목록) |
| `runtime/<작업>/` | llama-server 빌드, 불러온 모듈, 시작 때 GPU, 그리고 `sha256.txt`(llama.cpp 파일, 시험 묶음, 스크립트) |
| `runtime/<작업>/server/<모델>.cmd`, `.log.gz`, `.models.json`, `.gpu.txt` | 모델마다 서버 명령줄, 로그(gzip 사본), 모델 목록, 처음 답했을 때 GPU 메모리 |
| `job/<작업>.out` | 작업 출력 |
| [flow/](flow/) | 원기둥 계산: 작업 스크립트와 출력, 경우의 `system/`과 `constant/`(격자 제외), 로그마다 요약([summarize_cylinder_log.py](flow/summarize_cylinder_log.py)) |
| [cylinder_misses.py](cylinder_misses.py), [cylinder-misses.json](cylinder-misses.json) | 12B가 가장 낮은 압력을 놓쳤을 때 짚은 자리(8개는 원기둥 뒤쪽, 4개는 원기둥 아래 뒤편, 10개는 원기둥 아래), 그곳의 압력, 상태 열 개가 서로 얼마나 다른지; 릴리스에 있는 시험 묶음의 프레임이 필요함 |
| [cylinder-miss-analysis.json](cylinder-miss-analysis.json) | 원기둥에서 10 % 넘게 틀린 위치 답마다, 모델이 짚은 칸의 속력이나 압력을 참 극값에 대한 비로([../2026-10-22-window-test/miss_analysis.py](../2026-10-22-window-test/miss_analysis.py); 릴리스에 있는 시험 묶음의 프레임이 필요함) |
| [independent-recount.py](independent-recount.py), [independent-recount.json](independent-recount.json) | 시험 코드 없이 다시 세기(아래) |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

그림: `dev-sequence-v1-gap006000-steps102000-108000-114000-t1.png`\~`-t3.png`(한 묶음의 v1 그림 세 장:
최고 속력이 5.4 % 떨어지고 가장 낮은 압력이 32 % 올라감. 12B는 증가와 더 음수로 답함)와
`dev-sequence-v2own-...-t1-U.png`\~`-t3-p.png`(같은 묶음, 시각마다 |U|와 p를 제 색 범위로. 12B는 둘 다 맞힘);
`cylinder-flow-window-v2-step054000-w1-U.png` / `-p.png`와 `cylinder-flow-window-v1-step054000-w1.png`(원기둥
창 하나. 12B는 가장 낮은 압력을 참 칸에서 범위의 44 % 떨어진 뒤쪽 흐름(후류)에 짚음).

## 설정

- 모델: Gemma 줄은 10월 22일과 같은 `models.tsv`의 줄입니다. 4비트 Qwen 줄은 `qwen3vl-32b-q4`
  (`Qwen/Qwen3-VL-32B-Instruct-GGUF@e3e1fe0c…`, Q4_K_M), `qwen35-27b-q4`(`unsloth/Qwen3.5-27B-GGUF@3221f178…`,
  Q4_K_M), `qwen35-35b-q4`(`unsloth/Qwen3.5-35B-A3B-GGUF@bc014a17…`, Q4_K_M)이고, 저마다 제 프로젝터가 붙어
  있습니다. 모든 파일이 모델을 돌리기 전에 SHA-256 확인을 통과했습니다. 작업 24903975는 10월 22일의 Q8_0
  Qwen3.5-35B-A3B를 썼습니다.
- 서버: llama.cpp b11429(커밋 `d812350`), `--n-gpu-layers 99`, 슬롯 하나, reasoning 끔; 문맥 4096, 이미지 토큰
  한도 256. 단, 작업 24903976과 24903977은 문맥 8192, `--image-max-tokens 1024`와 `--image-min-tokens 1024`
  (llama.cpp 로그가 Qwen-VL 모델에 권하는 설정). `ab6b943`의 window_test.slurm은 `POD_HOST_MODULES`에 적은
  CUDA 모듈을 불러옵니다.
- 요청과 채점은 10월 22일과 같습니다: temperature 0, `max_tokens` 320, 시드 20261021, 프롬프트 캐시 없음;
  위치는 그린 범위의 10 % 안이면 맞음; 증감 단어는 정답의 기준(상대 변화 2 %, 자리는 범위의 5 %). 고정 답 열은
  묶음 전체에 답 하나만 쓴 가장 좋은 점수입니다.

## 다시 세기

`python3 independent-recount.py`(외부 패키지 불필요)는 `metrics.jsonl`과 정답만으로 보고서 다섯 개의 모든 수
칸을 다시 셉니다: 답한 수, 가장 빠른 곳과 가장 낮은 압력이 10 % 안인 수, 증감 단어 세 개, 고정 답 열. 보고서
다섯 개와 비교하면 38줄을 확인했고 다른 것은 없습니다. 보고서가 끌어 쓰는 수도 씁니다: 거리 중앙값, 뚜렷한
변화가 있는 묶음의 증감 단어, 모델마다 답한 단어, 같은 묶음의 10월 22일 수와 나란히 놓은 4비트 Qwen 수, 원기둥
극값의 자리. 토큰과 시간 열은 확인하지 않습니다.

## 참고

- 돌린 코드: `runtime/<작업>/sha256.txt`에 해시가 있는 스크립트는 모두 `ab6b943`과 같습니다(파일 38개 중
  38개). `developed-sequence` 묶음은 `6afbdeb`의 코드로(manifest의 해시 9개 중 9개가 같음), `cylinder` 묶음은
  `df72c24`와 같은 코드로(8개 중 8개) 만들었습니다(커밋은 영문 저장소의 것).
- 이 다섯 작업의 첫 제출(24903916\~24903920) 가운데 시작한 두 개(24903916과 24903920)는 1분 안에 멈췄습니다.
  작업 스크립트가 CUDA 모듈을 더 이상 불러오지 않아 서버가 `libcudart.so.12`를 찾지 못했습니다. 나머지 세 개는
  시작하기 전에 취소했습니다. 어느 것도 답을 내지 않아 남기지 않았고, 다시 낼 때 `POD_HOST_MODULES`를
  넣었습니다.
- 창 작업의 모델 폴더에는 돌리지 않은 묶음의 `summary.json`(시도 0개)도 있는데, 여기서는 뺐습니다.
- 원기둥 묶음의 manifest는 시험 이름을 "picture-window test 2026-10-22 (window seed 20261028)"이라고 적습니다.
  `window_test.py`가 쓰는 이름표이고, 묶음은 10월 27일에 만들었습니다.
- `truth.private.json`은 모델 입력에서 뺐다는 뜻이고, 개인 정보라는 뜻이 아닙니다.
- 기록에는 출처를 보이려고 클러스터 경로와 서버 프로세스 번호가 남아 있습니다.
