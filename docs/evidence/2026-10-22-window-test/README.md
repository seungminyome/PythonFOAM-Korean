# 10월 22일 근거: 무작위 창 그림 시험, Qwen 모델, 발달한 흐름

MedicineBow(와이오밍 대학교)의 Slurm 작업 여섯 개, 작업마다 NVIDIA RTX A6000 한 장(49,140 MiB), 2026-10-22
03:14~11:38 MDT, 그리고 그 작업들이 쓴 상태를 만든 흐름 계산 두 개입니다. 이 작업들에서는 솔버를 돌리지
않았습니다. v2 그림으로 한 솔버 실행은 [2026-10-22-live-v2](../2026-10-22-live-v2/README.md)에 있습니다.

[보고서](../../results-20261022-live.md) ·
[묶음을 만들고 돌리는 법](../../../Solver_Examples/PODFoam/llm_demo/hpc/README.md#무작위-창-시험과-qwen-모델-2026-10-22-실행) ·
[모든 압축 파일이 있는 릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/picture-test-2026-10-22) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-22-window-test/README.md)

## 작업

| 작업 | 요청 | 모델 | 시각(MDT) |
|---|---|---|---|
| 24757327 | 10월 22일 첫 시험의 요청 308개(`picture-test-20261021`) | Qwen3-VL-8B, Qwen3-VL-32B, Qwen3.5-27B, Qwen3.5-35B-A3B | 03:14~05:18 |
| 24757344 | `seed1`: 시작 직후 상태 12개, 상태마다 무작위 창 4개, v1과 v2(96개) | E2B(세 가지), E4B, 12B, 26B-A4B, 31B와 Qwen 모델 네 개 | 03:43~04:53 |
| 24757382 | `seed1`, 이미지 토큰 한도 1024, 문맥 8192 | 12B, 26B-A4B, 31B, Qwen3-VL-32B, Qwen3.5-27B, Qwen3.5-35B-A3B | 06:20~07:19 |
| 24757384 | `seed2`: 같은 상태, 다른 창(96개) | 같은 여섯 모델 | 06:21~07:17 |
| 24757383 | `seed3`: 같은 상태, 다른 창(96개) | 같은 여섯 모델 | 06:20~07:17 |
| 24757459 | `developed`: 발달한 흐름의 상태 35개, 상태마다 창 4개(280개) | 12B, 26B-A4B, 31B, Qwen3.5-35B-A3B, Qwen3.5-27B, E4B | 09:46~11:38 |
| 24757337 | 정지 상태에서 5e-7 s 간격 6000걸음의 `pimpleFoam`: `seed1`~`seed3`의 상태 | (CPU) | 03:35~03:41 |
| 24757429 | 시간 간격을 스스로 맞추며 t = 0.1 s까지 간 `pimpleFoam`: `developed`의 상태와 솔버 실행의 시작 | (CPU) | 08:52~09:11 |

창 시드: `seed1` 20261022, `seed2` 20261122, `seed3` 20261023, `developed` 20261025(릴리스의 묶음 이름
`-s2`, `-s3`은 시드 순서와 다릅니다). 상태: `seed1`~`seed3`은 500걸음부터 6000걸음까지 500걸음마다
(t = 0.25~3 ms), `developed`는 5e-7 s 걸음으로 64000부터 200000까지 4000걸음마다(t = 0.032~0.1 s).

## 파일

| 경로 | 내용 |
|---|---|
| `reports/<작업>.md` | 작업이 직접 쓴 보고서(`picture_test.py report` 또는 `window_test.py report`): 모델·묶음별 수, 고정 답 열, 토큰과 시간 중앙값 |
| `results/<작업>/<모델>/run.json` | 모델 이름, 서버 설명(저장소, 리비전, 파일, 설정), 묶음, 시간 제한, 시험 묶음 manifest와 정답의 해시 |
| `results/<작업>/<모델>/<묶음>/metrics.jsonl`, `summary.json` | 요청마다 한 줄: 해석한 답과 점수, 보낸 요청과 준비한 요청의 해시, 토큰, 서버 시간, 벽시계 시간; 실행기의 묶음 요약 |
| `results/picture-test-24757327/<모델>/oct17-paired*/<요청>/result.json` | 10월 17일 답마다 클라이언트 기록 |
| `test-sets/<묶음>/manifest.json`, `truth.private.json` | `seed1`, `seed2`, `seed3`, `developed`의 manifest(요청 해시, 만든 인자, 창 규칙, 코드 해시)와 정답. 요청 308개의 정답은 [../2026-10-22-picture-test/test-set/](../2026-10-22-picture-test/test-set/)에 있음 |
| [pictures/](pictures/) | 요청 본문에서 풀어낸, 보낸 그대로의 그림(아래 목록) |
| `runtime/<작업>/` | llama-server 빌드, 불러온 모듈, 시작 때 GPU, 그리고 `sha256.txt`(llama.cpp 파일, 시험 묶음, 작업이 돌린 스크립트의 해시) |
| `runtime/<작업>/server/<모델>.cmd`, `.log.gz`, `.models.json`, `.gpu.txt` | 모델마다 서버 명령줄, 로그(gzip 사본), 띄운 모델 목록, 처음 답했을 때 GPU 메모리 |
| `job/<작업>.out` | 작업이 자기 압축 파일에 복사해 둔 작업 출력 |
| [flow/](flow/) | 흐름 계산 두 개의 작업 스크립트와 출력, 발달한 경우의 설정(`system/`, `constant/`)과 로그 요약 |
| `miss-analysis/<작업>.json`, [miss_analysis.py](miss_analysis.py) | 창 작업에서 10 % 넘게 틀린 위치 답마다, 모델이 짚은 칸의 속력(또는 압력)을 참 극값에 대한 비로. 스크립트에는 릴리스에 있는 시험 묶음의 프레임이 필요함 |
| [independent-recount.py](independent-recount.py), [independent-recount.json](independent-recount.json) | 시험 코드 없이 다시 세기(아래) |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

그림: `seed1-flow-window-v1-step003000-w4.png`와 `seed1-flow-window-v2-step003000-w4-U.png` / `-p.png`(같은
요청을 두 방식으로. 12B는 v1에서 26 %, v2에서 1.9 % 떨어짐); `developed-flow-window-v2-step080000-w3-U.png` /
`-p.png`(12B가 0.4 % 안); `developed-flow-window-v2-step124000-w1-U.png`(12B가 61 % 떨어짐. 가장 밝은 점(y 19 %)이
그 위 자유 흐름보다 조금밖에 밝지 않은데, 답은 그 자유 흐름을 짚음).

## 설정

- 모델: Gemma 줄은 [10월 22일 첫 시험](../2026-10-22-picture-test/README.md#설정)과 같습니다. Qwen 줄은 저마다
  제 프로젝터가 붙은 Q8_0 빌드입니다: `Qwen/Qwen3-VL-8B-Instruct-GGUF@f982a075…`,
  `Qwen/Qwen3-VL-32B-Instruct-GGUF@e3e1fe0c…`, `unsloth/Qwen3.5-27B-GGUF@3221f178…`,
  `ggml-org/Qwen3.5-35B-A3B-GGUF@3127ef0b…`. 모든 파일이 모델을 돌리기 전에 SHA-256 확인을 통과했습니다.
- 서버: llama.cpp b11429(커밋 `d812350`), `--n-gpu-layers 99`, 문맥 4096, batch와 ubatch 512, 이미지 토큰
  한도 256, 슬롯 하나, reasoning 끔. 작업 24757382는 이미지 토큰 한도 1024, 문맥 8192.
- 요청과 채점은 첫 시험과 같습니다: temperature 0, `max_tokens` 320, 시드 20261021, 프롬프트 캐시 없음,
  그린 범위의 10 % 안이면 맞음. 창 묶음에서는 요청마다 그린 범위가 다르므로, 고정 답 열은 묶음 전체에
  정수 답 하나만 쓴 가장 좋은 점수입니다.

## 다시 세기

`python3 independent-recount.py`(외부 패키지 불필요)는 `metrics.jsonl`과 정답만으로 보고서 여섯 개의 모든 수
칸을 다시 셉니다: 답한 수, 가장 빠른 곳과 가장 낮은 압력이 10 % 안인 수, 증감 단어 세 개, 고정 답 열, 그리고
요청 308개의 10월 17일 "located" 수(이것은 실행기의 위치 항목에서 읽음). 보고서 여섯 개와 비교하면 134줄을 확인했고 다른 것은 없습니다. 보고서가 끌어 쓰는
수도 씁니다: 거리 중앙값, 뚜렷한 증감 수, 시드 세 개 합계, 묶음마다 가장 빠른 칸이 있는 자리. 토큰과 시간
열은 확인하지 않습니다.

## 참고

- 창 시험 보고서의 각주는 고정 답 열을 "그린 범위마다 답 하나로 고정했을 때"라고 적습니다. 실제 열은 위에
  적은 대로 묶음 전체에 답 하나입니다. 이 표기는 이 작업들 뒤에 `window_test.py`에서 고쳤습니다. 숫자는
  다시 세기가 확인합니다.
- 창 작업의 모델 폴더에는 돌리지 않은 요청 308개 시험 묶음의 `summary.json`(시도 0개)도 있는데, 여기서는
  뺐습니다.
- 작업 압축 파일에는 서버 로그 사본이 하나 더 있습니다(모델 이름으로, 서버를 멈추기 전에 복사). 여기 둔
  시각 이름 로그는 끝까지 다 있습니다.
- llama.cpp 로그는 Qwen 모델마다, Qwen-VL 모델은 위치를 짚는 일에 이미지 토큰이 최소 1024개 필요하다고
  경고하고 `--image-min-tokens 1024`를 권합니다. 이 옵션은 쓰지 않았습니다.
- 돌린 코드: 그림 시험 묶음에 든 `58e00d9`의 `llm_demo` 폴더에 `window_test.py`와 `window_test.slurm`을
  더하고, `models.tsv`에 Qwen 줄을 넣고, 작업 24757382부터는 `start_server.sh`가 `LLM_IMAGE_TOKENS`를 읽게 한
  것입니다. 스크립트마다의 해시는 `runtime/<작업>/sha256.txt`에 있습니다. 작업 24757459는 솔버 실행의
  체크아웃에서 돌았습니다([2026-10-22-live-v2](../2026-10-22-live-v2/README.md) 참고).
- `seed1`~`seed3`은 그림 시험 묶음의 코드에 `window_test.py`를 더해, `developed`는 요청 빌더가
  `readable_request.py`로 옮겨 간 뒤 솔버 실행의 코드로 만들었습니다. 해시는 manifest마다 있습니다.
  프롬프트와 그림 방식은 같습니다.
- `truth.private.json`은 모델 입력에서 뺐다는 뜻이고, 개인 정보라는 뜻이 아닙니다.
- 기록에는 출처를 보이려고 클러스터 경로와 서버 프로세스 번호가 남아 있습니다.
