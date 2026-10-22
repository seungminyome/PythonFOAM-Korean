# 10월 22일 근거, GPU 노드의 그림 읽기 시험

MedicineBow(와이오밍 대학교)의 Slurm 작업 24756981, NVIDIA RTX A6000 한 장(49,140 MiB). 2026-10-22에
모델 실행은 01:20부터 02:43 MDT까지였고, 결과는 02:45에 릴리스에 올라갔습니다. `picture_test.py`로
미리 만든 같은 요청 308개를 Gemma 4 모델 일곱 개에 차례로 보냈습니다. 솔버는 돌리지 않았습니다.
코드는 영문 저장소의 `58e00d9`이고, 이 저장소에서 같은 코드는 `7435513`입니다.

[보고서](../../results-20261022.md) ·
[묶음을 만들고 돌리는 법](../../../Solver_Examples/PODFoam/llm_demo/hpc/README.md#그림-읽기-시험-2026-10-22-실행) ·
[두 압축 파일이 있는 릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/picture-test-2026-10-22) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-22-picture-test/README.md)

## 파일

| 파일 | 내용 |
|---|---|
| [report.md](report.md) | 작업이 직접 쓴 요약(`picture_test.py report`): 모델·묶음·모드별 맞힌 수, 답을 하나로 고정했을 때의 점수, v1/v2와 v2/v2own 문항별 비교, 공개된 E2B 답과 같은 답의 수 |
| `results/<모델>/run.json` | 모델 이름, 서버 설명(저장소, 리비전, 파일, 서버 설정), 묶음 목록, 마감, 시험 묶음 manifest와 정답 파일의 해시 |
| `results/<모델>/<묶음>/metrics.jsonl` | 요청마다 한 줄: 해석한 답과 정답에 비춘 점수, 보낸 요청과 준비한 요청의 해시, 프롬프트·생성 토큰 수, 서버 시간, 걸린 시간. 10월 17일 두 묶음은 해석한 답과 점수 대신 위치 검사와 근거 검사가 들어 있습니다. |
| `results/<모델>/oct17-paired*/<요청>/result.json` | 10월 17일 쌍별 요청에 대한 답마다 클라이언트 기록. 답의 원문과 해석한 항목이 들어 있습니다. |
| `results/<모델>/<묶음>/summary.json` | 그 묶음에 대한 실행기의 요약 |
| [test-set/manifest.json](test-set/manifest.json), [test-set/truth.private.json](test-set/truth.private.json) | 시험 묶음의 manifest(요청 해시, 만든 인자, 코드 해시)와 정답 |
| [pictures/](pictures/) | 보낸 그림 일곱 장. 요청 본문에서 풀어낸 것 |
| [runtime/server/](runtime/server/) | 모델마다 llama-server 명령줄, 로그, 서버가 내놓은 모델 목록, 서버가 처음 준비됐을 때의 GPU 메모리(파일 이름에 붙은 시각은 아래 참고) |
| [runtime/llama-server-version.txt](runtime/llama-server-version.txt), [modules.txt](runtime/modules.txt), [nvidia-smi.txt](runtime/nvidia-smi.txt), [sha256.txt](runtime/sha256.txt) | llama-server 빌드, 불러온 모듈, 시작할 때의 GPU, llama.cpp 폴더·시험 묶음·스크립트의 해시 |
| [job/job-so-far.out](job/job-so-far.out) | 결과를 묶을 때 복사한 작업 로그 |
| [independent-rescore.py](independent-rescore.py), [independent-rescore.json](independent-rescore.json) | `picture_test.py` 없이 다시 채점한 것. `report.md`의 맞힌 수를 모두 답과 정답으로 다시 계산하고(답한 수는 답의 상태로), 고정 답 열과 문항별 비교 줄도 확인합니다(518개 확인, 다른 것 없음). 보고서가 쓰는 다른 수(합계, 거리, 추세 설계, 심은 그림을 틀린 답, 10월 17일의 답, 시간과 메모리)도 냅니다. 토큰과 시간 열, 공개된 답과의 비교는 확인하지 않습니다. 이 폴더에서 실행합니다. |
| [manifest.json](manifest.json) | 이 폴더 파일의 출처, 크기, 해시 |

`runtime/server/` 파일 이름의 시각: `20261022T072022Z` e2b, `T072559Z` e2b-bf16, `T073132Z`
e2b-qat, `T073701Z` e4b, `T074412Z` 12b, `T075904Z` 26b, `T081056Z` 31b.

## 설정

- 시험 묶음 `picture-test-20261021`: manifest `52430fe7…`, 정답 `01ecaed3…`. 작업은 첫 모델을 띄우기
  전에 `picture_test.py check`를 돌렸고, 요청 308개를 확인해 문제가 0개였습니다. 모델 파일도 모두
  SHA-256 확인을 통과했습니다.
- 모델(`run.json`에서):

  | 키 | 서버 이름 | 저장소 @ 리비전, 파일 |
  |---|---|---|
  | e2b | `gemma-4-E2B-it-Q4_0-vision` | `ggml-org/gemma-4-E2B-it-GGUF@b4243c15…`, `gemma-4-E2B-it-Q4_0.gguf` + `mmproj-gemma-4-E2B-it-Q8_0.gguf` |
  | e2b-bf16 | `gemma-4-E2B-it-Q4_0-bf16proj-vision` | 같은 저장소와 가중치 + `mmproj-gemma-4-E2B-it-BF16.gguf` |
  | e2b-qat | `gemma-4-E2B-it-qat-q4_0-vision` | `google/gemma-4-E2B-it-qat-q4_0-gguf@675cff42…` |
  | e4b | `gemma-4-E4B-it-qat-q4_0-vision` | `google/gemma-4-E4B-it-qat-q4_0-gguf@4b4a2c1d…` |
  | 12b | `gemma-4-12b-it-qat-q4_0-vision` | `google/gemma-4-12B-it-qat-q4_0-gguf@29d09777…`, 2026-10-19와 같은 파일 |
  | 26b | `gemma-4-26B-A4B-it-qat-q4_0-vision` | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf@d1c082be…` |
  | 31b | `gemma-4-31B-it-qat-q4_0-vision` | `google/gemma-4-31B-it-qat-q4_0-gguf@59dde245…` |

- 모델마다 작업이 서버를 새로 띄웠습니다. llama.cpp b11429(커밋 `d812350`, 2026-10-19의 소스 빌드),
  `--n-gpu-layers 99`, 문맥 4096, batch와 ubatch 512, 이미지 토큰 상한 256, 슬롯 하나, reasoning 끔,
  포트 26981. 명령줄은 `runtime/server/*.cmd`에 있습니다. GPU 메모리 줄은 서버가 처음 `/health`에
  답했을 때, 요청을 보내기 전에 적은 것입니다.
- 프로젝터 종류는 나중에 Hugging Face에 있는 고정 리비전 파일의 GGUF 머리 부분에서 읽었습니다(작업은
  기록하지 않음). e2b는 Q8_0, 나머지는 모두 BF16입니다. e2b-qat의 프로젝터는 Google이 따로 낸
  파일이고, e2b-bf16의 BF16 파일과는 다른 파일입니다.

## 참고

- 입력 묶음(`pythonfoam-picture-test-20261021.tar.gz`, sha256 `b4a3e332…`)에는 커밋 `58e00d9`의
  `llm_demo` 폴더(git archive), 시험 묶음, 한국어 안내(`README.ko.md`), `SOURCE.txt`, `SHA256SUMS`가
  들어 있습니다. [runtime/sha256.txt](runtime/sha256.txt)에서 스크립트는 `hpc/picture_test.slurm`
  (`de18f174…`) 하나만 빼고 모두 그 커밋과 같습니다. 이 파일은 클러스터에서 사이트 줄(module과
  PATH)을 고쳤고, 결과에는 들어 있지 않습니다.
- 작업은 RTX A6000에서 돌았습니다. 안내에는 A30 파티션을 적었고, 실제로 어느 파티션이었는지는
  기록에 없습니다.
- 작업 압축 파일(`picture-test-24756981.tar.gz`, sha256 `a8ea6c79…`, 릴리스에 있음)에는 요청마다
  원본 답, 해석한 답, 클라이언트 기록과 그 지표도 들어 있습니다. 이 폴더에는 그중 10월 17일 답의
  클라이언트 기록만 넣었습니다. 보낸 요청 본문은 남기지 않았습니다. 준비한 본문에서 `model`만 바꾼
  것이고, `metrics.jsonl`에 두 해시가 모두 있습니다.
- 압축 파일에는 서버 로그, 명령줄, 모델 목록, GPU 줄의 복사본이 모델 이름으로 하나씩 더 있습니다.
  그 로그는 서버를 멈추기 전에 복사한 것이라 `server/`의 로그 앞부분과 같고 73~74바이트 짧으며,
  나머지 세 파일은 똑같습니다. 여기에는 `server/`의 것만 넣었습니다.
- 원래 이름이 `*.log`인 파일은 `.gitignore`가 `*.log`를 빼므로 `.txt`로 저장했습니다. 내용은 같습니다.
- `job-so-far.out`은 보고서를 출력한 뒤에 복사한 것이라, 결과를 묶고 올리는 단계의 줄은 들어 있지
  않습니다.
- `oct17-paired`와 `oct20-replay`는 공개된 요청 본문에서 모델 이름만 바꾼 것이라 서버의 프롬프트
  캐시를 씁니다. `oct17-paired-cold`와 새 묶음은 `cache_prompt: false`를 보냅니다.
- `truth.private.json`의 private는 모델 입력에서 뺐다는 뜻이고, 개인 정보라는 뜻이 아닙니다.
- 기록에는 어디서 나왔는지 알 수 있도록 클러스터 경로와 서버 PID가 남아 있습니다.
