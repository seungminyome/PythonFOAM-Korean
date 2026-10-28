# GPU 노드에서 12B 모델 돌리기

E2B로 잰 것을 Gemma 4 12B QAT Q4_0으로 클러스터 GPU에서 다시 재는 스크립트입니다.
쌍별 재생은 2026-10-17의 요청을 모델 이름만 바꿔 보냅니다. 솔버와 콜백 코드는 2026-10-17
이후 바뀌었으므로(`9449085`, 영문 저장소) `demo_12b.slurm`은 10월 17일의 코드를 다시 돌리는 것이
아닙니다.

쌍별 재생은 MedicineBow에서 한 번 돌렸습니다(2026-10-19). [시험한 곳](#시험한-곳)과
[기록](../../../../docs/evidence/2026-10-19-12b/README.md)을 보세요.

| 스크립트 | 하는 일 |
|---|---|
| `setup_12b.sh` | llama.cpp b11429 CUDA 빌드와 12B 가중치·이미지 프로젝터를 `google/gemma-4-12B-it-qat-q4_0-gguf`에서 내려받고, 이것들과 쓰고 있는 `llama-server`의 SHA-256을 기록. 약 8 GB. |
| `start_server.sh` / `stop_server.sh` | 노드 GPU에서 llama-server를 E2B와 같은 설정(문맥 2048, 슬롯 1, 이미지 토큰 256 요청, reasoning off)으로 띄움. 모든 층을 GPU에. `server.pid` 기록. 12B 프로젝터에서는 `--ubatch-size`가 128이라서 서버가 이미지 토큰 상한을 128로 낮춤. |
| `replay_12b.slurm` | 2026-10-17의 5단계 상태로 쌍별 재생: 수치만 vs 수치+그림 세 쌍, 시드 20261017. OpenFOAM 불필요. |
| `demo_12b.slurm` | 연결 검증, 솔버 다섯 조건, 검증, 새 상태의 쌍별 재생. 노드에 OpenFOAM v2106 필요. |
| `picture_test.slurm`, `fetch_models.sh`, `models.tsv` | 여러 크기의 모델로 하는 그림 읽기 시험(2026-10-21 준비, 2026-10-22 실행). [아래](#그림-읽기-시험-2026-10-22-실행) 참고. |
| `window_test.slurm` | `MODELS`의 모델로 하는 무작위 창 그림 시험(`window_test.py`). [아래](#무작위-창-시험과-qwen-모델-2026-10-22-실행) 참고. |
| `async_v2.slurm` | 발달한 흐름에서 시작해, 돌고 있는 솔버가 그린 v2 그림과 Gemma 4 12B로 하는 비동기 시험, 이어서 describe sweep. OpenFOAM은 Apptainer 이미지에서, llama-server는 호스트 GPU에서. [아래](#돌고-있는-솔버가-그린-v2-그림-async_v2slurm-2026-10-22-실행) 참고. |
| `periodic_v2.slurm` | v2 describe 요청을 N걸음마다 보내는 긴 실행과 요청 없는 쌍둥이(`run_periodic.py`). `async_v2.slurm` 실행의 기준 준비 폴더에서 시작. 비용, 메모리, 파이프 전송량. |
| `build_llama_cuda.sh` | 예비: 미리 빌드된 바이너리가 안 돌면(glibc가 오래됨, CUDA 버전 다름) b11429를 소스에서 CUDA로 빌드. |

## 파일을 클러스터에 올리는 법

둘 다 됩니다. 작업 스크립트가 폴더 구조를 알아서 찾습니다.

```bash
git clone https://github.com/seungminyome/PythonFOAM.git && cd PythonFOAM
# 또는: tar -xzf pythonfoam-12b-hpc-20261019.tar.gz && cd pythonfoam-12b-hpc
```

재생에 쓰는 저장 상태는 저장소 안에 있으므로
(`docs/evidence/2026-10-17/pod-llm-demo.LRfJBN/fixed-pod`) clone이면 더 필요한 게
없습니다. 계산 노드에 인터넷이 없으면 제출 전에 로그인 노드에서 한 번 내려받으세요.

```bash
export HF_TOKEN=hf_... POD_LLM_RUNTIME=$PWD/llm-runtime-12b
bash Solver_Examples/PODFoam/llm_demo/hpc/setup_12b.sh
```

## 제출 전에

1. [huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)에서
   Gemma 라이선스에 동의하고 read 토큰을 만든 뒤, 제출하는 셸에서 `export HF_TOKEN=hf_...`.
2. `.slurm` 파일의 클러스터 설정 줄을 고침 (CUDA 12.8 또는 13.4, numpy 있는 Python 3;
   demo는 matplotlib과 OpenFOAM v2106도 필요). `LLAMA_CUDA=13.4`는 CUDA 13 빌드를 고르며, 드라이버 580 이상이 필요함.
3. 파티션과 `--gres` 표기가 클러스터와 맞는지 확인. 계정과 파티션은 `sbatch` 명령줄에서 줌.
4. `HF_TOKEN`은 가중치가 아직 `POD_LLM_RUNTIME`에 없을 때만 필요.

## 제출

```bash
# 저장소 루트(또는 tar.gz를 푼 루트)에서
export HF_TOKEN=hf_...
sbatch Solver_Examples/PODFoam/llm_demo/hpc/replay_12b.slurm   # GPU 1장. 런타임이 준비돼 있으면 A30에서 35 s
sbatch Solver_Examples/PODFoam/llm_demo/hpc/demo_12b.slurm     # OpenFOAM v2106이 있을 때만
# tar.gz를 풀었으면 경로는 PODFoam/llm_demo/hpc/...
```

결과는 `results/`에 생김: `replay-12b-<jobid>.tar.gz`(요청 6개, 답, `summary.json`,
`manifest.json`, GPU 이름, 런타임 manifest)와 `demo-12b-<jobid>.tar.gz`(검증 JSON,
시간, `run-archive.tar.gz`, 새 상태의 재생).

## 무엇을 비교하나

- 재생: `summary.json`의 `numeric_only`와 `numeric_plus_image`, 위치 오차는
  `ground_truth.private.json` 기준(참값 x = 0.000538 m, y = 0.01271 m).
  이 상태에서 E2B는 60.92 cm와 50.97 cm였음. A30의 12B는 여섯 답 모두 위치를 모른다고 해서
  채점된 것이 없음.
- demo: `timings.json`의 조건별 `cpp_measured_full_callback_s`
  (CPU의 E2B: 0.49 / 78.26 / 39.67 / 0.51 / 4.01 s), `demo-verification.json`의
  `status`가 `PASS`이고 같은 파일 45개.
- 각 결과의 `server_timings.cache_n`: 0이나 1이면 프롬프트 캐시가 비어 있었다는 뜻(새로 띄운
  서버에서는 0, 12B 실행이 그랬음).

## 그림 읽기 시험 (2026-10-22 실행)

`picture_test.slurm`은 미리 만든 요청 308개를 `MODELS`의 모델마다, GPU 하나에서 차례로
보냅니다. 요청 묶음은 클러스터 밖의 컴퓨터에서 `picture_test.py build`로 만들고(matplotlib 필요)
클러스터로 옮깁니다. 작업 자체에는 numpy가 있는 Python 3만 있으면 되고 OpenFOAM은
필요 없습니다.

| 묶음 | 요청 | 내용 |
|---|---:|---|
| `oct17-paired` | 6 | 2026-10-17 쌍별 요청. 모델 이름만 바뀜 |
| `oct17-paired-cold` | 6 | 같은 여섯 개에 `cache_prompt: false` |
| `oct20-replay` | 24 | 2026-10-20 describe·sequence 요청. 모델 이름만 바뀜 |
| `control-position-v1`, `-v2` | 각 32 | 정해 둔 자리에 \|U\|의 밝은 점 하나와 p의 어두운 점 하나를 넣은 합성 필드. 전체 영역과 창 |
| `planted-position-v1`, `-v2` | 각 32 | 저장 상태(1000·2500·4000·5500걸음)에 좁은 \|U\| 봉우리와 p 골을 하나씩, 계단 모서리에서 15 % 이상 떨어진 곳에 넣은 것 |
| `control-trend-v1`, `-v2`, `-v2own` | 각 18 | 세 시각의 합성 필드. 속력 추세 × 압력 추세 × 점의 움직임 조합마다 한 번 |
| `flow-describe-v1`, `-v2` | 각 24 | 6000걸음까지 500걸음마다의 저장 상태. 전체 영역과 창 |
| `flow-sequence-v1`, `-v2`, `-v2own` | 각 14 | 저장 상태 세 개씩 일곱 묶음. 전체 영역과 창 |

v1은 솔버가 보내는 그림입니다(`pod_image.py`: 패널 두 개, 640x360, 색 범위는 그림마다).
v2는 `readable_image.py`가 그립니다. 그림 한 장에 필드 하나만 1024x576 크기로 그리고, 축은 그린 범위의
퍼센트로 적고 10 %마다 격자선을 그으며, 색 막대에는 최솟값부터 최댓값까지 값 다섯 개를 적습니다.
sequence에서는 모든 프레임이 같은 색 범위를 씁니다. v2own은 v2에서 색 범위만 그림마다 따로 잡은
것이고, 프롬프트도 색 범위 문장과 추세를 무엇으로 판단하라는 말(색인지 색 막대 숫자인지)만
다릅니다. 그래서 v2와 v2own을 비교하면 모든 프레임이 색 범위 하나를 같이 쓰는 것의 효과만 따로 볼
수 있습니다. v2는 v1보다 이미지 토큰을 다섯 배쯤 더 씁니다. 새 묶음은 `cache_prompt: false`를 보내서
프롬프트를 매번 처음부터 처리합니다. 흐름 상태는 모델 요청 없이 돌린 PODFoam 실행에서 왔습니다
(5e-7 s 6000걸음, 250걸음마다 저장. 앞의 저장 시각 12개는 2026-10-20 실행과 같음). 모든 흐름
상태에서 가장 빠른 곳과 압력이 가장 낮은 곳은 계단 모서리이고, 추세 단어도 거의 모든 연속 그림에서
같아서, 요약마다 답을 하나로 고정했을 때의 점수(`constant_answer_baseline`)를 함께 적습니다. 그림을
정말 읽는지는 합성 묶음과 심은 묶음에서 가릴 수 있습니다.

모델(`models.tsv`에 리비전과 SHA-256 고정. 토큰이 필요한 저장소는 없음):

| 키 | 저장소, 파일 | 내려받기 |
|---|---|---:|
| `e2b` | `ggml-org/gemma-4-E2B-it-GGUF`, Q4_0 + Q8_0 프로젝터. CPU에서 써 온 파일 | 3.4 GB |
| `e2b-bf16` | 같은 Q4_0 가중치 + 같은 저장소의 BF16 프로젝터 | 1.0 GB 더 |
| `e2b-qat` | `google/gemma-4-E2B-it-qat-q4_0-gguf`, BF16 프로젝터 | 4.3 GB |
| `e4b` | `google/gemma-4-E4B-it-qat-q4_0-gguf`, BF16 프로젝터 | 6.1 GB |
| `12b` | `google/gemma-4-12B-it-qat-q4_0-gguf`. 2026-10-19와 같은 파일 | 7.2 GB |
| `26b` | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf`, BF16 프로젝터 | 15.6 GB |
| `31b` | `google/gemma-4-31B-it-qat-q4_0-gguf`, BF16 프로젝터 | 18.9 GB |
| `qwen3vl-8b` | `Qwen/Qwen3-VL-8B-Instruct-GGUF`, Q8_0 + F16 프로젝터(2026-10-22 추가) | 9.9 GB |
| `qwen3vl-32b` | `Qwen/Qwen3-VL-32B-Instruct-GGUF`, Q8_0 + F16 프로젝터 | 36.0 GB |
| `qwen35-27b` | `unsloth/Qwen3.5-27B-GGUF`, Q8_0 + BF16 프로젝터(제3자 변환) | 29.5 GB |
| `qwen35-35b` | `ggml-org/Qwen3.5-35B-A3B-GGUF`, Q8_0 + Q8_0 프로젝터 | 37.5 GB |
| `qwen3vl-32b-q4` | 같은 저장소, Q4_K_M + F16 프로젝터(2026-10-27 추가, Gemma QAT 파일과 같은 가중치 정밀도) | 21.0 GB |
| `qwen35-27b-q4` | `unsloth/Qwen3.5-27B-GGUF`, Q4_K_M + BF16 프로젝터 | 17.7 GB |
| `qwen35-35b-q4` | `unsloth/Qwen3.5-35B-A3B-GGUF`, Q4_K_M + BF16 프로젝터 | 22.9 GB |

e2b와 e2b-bf16은 프로젝터만 다릅니다. e2b-qat는 가중치가 다르고, 프로젝터도 Google이 따로 낸
파일입니다(e2b-bf16과 마찬가지로 BF16). 서버 설정은 모든 모델이 같습니다. 문맥 4096(그림 여섯 장인
v2 sequence가 프롬프트 약 2,200토큰), batch와 ubatch 512(어느 프로젝터도 이미지 토큰 상한 256을
낮추지 않게), 모든 층을 GPU에. 나머지는 `start_server.sh`와 같습니다. 작업은 자기 서버의 pid 파일,
로그, 띄운 시각을 적은 `server.stamp`를 `results/picture-test-<작업번호>/server/`(`POD_LLM_STATE`)에
두고, 포트는 20000 + 작업번호를 10000으로 나눈 나머지를 써서 다른 작업의 서버와 섞이지 않습니다.

```bash
# 클러스터에서, 묶음을 푼 폴더에서
export POD_LLM_RUNTIME=<12B 때 만든 llama-b11429-cuda/가 있는 폴더>
bash PODFoam/llm_demo/hpc/fetch_models.sh e2b e2b-bf16 e2b-qat e4b 12b 26b 31b   # 계산 노드에 인터넷이 없으면 로그인 노드에서
sbatch --account=<계정> --partition=mb-a30 PODFoam/llm_demo/hpc/picture_test.slurm
# 모델 몇 개만: sbatch --export=ALL,MODELS="e2b 12b" ...
```

결과는 `results/picture-test-<작업번호>.tar.gz`에 모입니다. 모델마다 폴더가 하나 있고, 그 안에 묶음별
`summary.json`, `metrics.jsonl`, 모든 답이 있습니다. 보낸 요청 본문은 준비한 본문에서 모델 이름만 바꾼
것이라 빼고, SHA-256만 `metrics.jsonl`에 남깁니다. 그 밖에 모델별 서버 로그와 명령줄,
`llama-server-version.txt`, `nvidia-smi.txt`, `modules.txt`, `sha256.txt`(llama.cpp 폴더, 시험 묶음,
스크립트), 실패가 있으면 `failed.txt`, 그때까지의 작업 로그, `report.md`가 들어 있습니다.
`report.md`(`picture_test.py report`)에는 시도한 요청 수 기준 점수, 고정 답 점수, v1/v2와 v2/v2own
문항별 비교, 모델마다 2026-10-17/20 답 중 공개된 E2B 답과 같은 답의 수가 있습니다. `GH_TOKEN`
(contents 쓰기 권한)과 `RESULTS_RELEASE=<태그>`를 주면 결과 묶음을 그 GitHub 릴리스에 올립니다.
`CLEANUP_MODELS=1`이면 이 작업이 직접 받은 모델 파일(`fetched.txt`)만, `CLEANUP_MODELS=all`이면
`MODELS`에 있는 키의 `models/<키>` 폴더를 모두 지웁니다. 12B 파일은 지우지 않습니다. 다른 작업이 같은
`POD_LLM_RUNTIME`을 쓰는 동안에는 둘 다 쓰지 마세요. 작업은 모델을 띄우기 전에
`picture_test.py check`로 요청 파일과 정답 파일이 모두 manifest와 같은지 확인합니다.

2026-10-22에 Slurm 작업 24756981로 NVIDIA RTX A6000 한 장(49,140 MiB)에서 돌렸습니다. 스케줄러가
mb-a30 대기열에서는 2주 뒤에야 시작한다고 예상해서 mb-a6000 파티션에 제출했습니다. 모델 일곱 개가
저마다 요청 308개에 모두 답했고, 모델 일곱 개를 돌린 시간은 모델을 띄우는 시간까지 합쳐
83분이었습니다. llama.cpp b11429에서 모든 모델이 떠서 답했고, 26B-A4B와 31B도 마찬가지였습니다.
31B는 서버가 처음 준비됐을 때 GPU 메모리 20,128 MiB를 쓰고 있었습니다. A30의 24 GB에 31B가
들어가는지는 해 보지 않았습니다. 결과: [10월 22일 보고서](../../../../docs/results-20261022.md),
[근거](../../../../docs/evidence/2026-10-22-picture-test/README.md).

## 무작위 창 시험과 Qwen 모델 (2026-10-22 실행)

그림 시험의 흐름 상태에서는 가장 빠른 곳과 압력이 가장 낮은 곳이 계단 모서리에 있어서, 답 하나로 고정해도
24개 중 24개를 맞힙니다. `window_test.py`는 같은 상태를 그리되 창을 가장 빠른 칸 둘레에 무작위로 놓아,
그림마다 정답 자리가 달라지게 합니다([llm_demo README](../README.md#무작위-창-그림-시험-window_testpy) 참고).
`window_test.slurm`은 `picture_test.slurm`처럼 묶음 하나를 돌리고, 이미지 토큰 한도를 시험하려면
`LLM_CTX`와 `LLM_IMAGE_TOKENS`(기본 4096과 256, `start_server.sh`가 읽음)를 올릴 수 있습니다.
`LLM_IMAGE_MIN_TOKENS`는 `--image-min-tokens`를 넘깁니다(llama.cpp가 Qwen-VL에 권하는 1024).
`PICTURE_TEST_SCRIPT=sequence_test.py`이면 `sequence_test.py`로 만든 변화 읽기 묶음을 돌립니다.

```bash
python3 Solver_Examples/PODFoam/llm_demo/window_test.py build --states <case> \
    --centres docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz \
    --old-manifest <picture-test-20261021/manifest.json> --output <set> [--seed N] [--first-step N --describe-every N --last-step N]
export POD_LLM_RUNTIME=$PWD/llm-runtime-12b PICTURE_TEST_SET=<set>
sbatch --export=ALL,MODELS="12b 26b 31b qwen35-35b" --account=<account> --partition=mb-a6000 \
    Solver_Examples/PODFoam/llm_demo/hpc/window_test.slurm
```

2026-10-22에 모두 RTX A6000 한 장에서 돌렸습니다. 그림 시험 요청 308개에 Qwen 모델 네 개(작업 24757327);
시작 직후 상태(v2212 이미지에서 5e-7 s 간격 6000걸음을 돌린 `pimpleFoam` 실행, 작업 24757337, 500걸음마다
상태)에 무작위 창 네 개씩(요청 96개)으로 모델 열한 개(작업 24757344); 가장 큰 여섯 모델을 다른 창 시드
두 개로(작업 24757384, 24757383), 그리고 `LLM_IMAGE_TOKENS=1024 LLM_CTX=8192`로(작업 24757382) 다시;
발달한 흐름(아래)의 상태 35개에 창 네 개씩(요청 280개, 작업 24757459). 결과:
[보고서](../../../../docs/results-20261022-live.md), [근거](../../../../docs/evidence/2026-10-22-window-test/README.md).

## 돌고 있는 솔버가 그린 v2 그림 (`async_v2.slurm`, 2026-10-22 실행)

MedicineBow에는 OpenFOAM 모듈이 없지만, OpenFOAM v2212가 Apptainer 이미지(그곳에서 solids4foam에 쓰는
것)로 돕니다. PODFoam은 numpy와 matplotlib가 있는 conda Python 3.11에 맞춰 그 안에서 고치지 않고
빌드되고(이미지에는 Python이 없음), 연결 검증도 그 안에서 통과합니다.

```bash
module load apptainer
apptainer exec <of2212.sif> bash -c '
    source /usr/lib/openfoam/openfoam2212/etc/bashrc
    export LD_LIBRARY_PATH=<conda>/lib:$LD_LIBRARY_PATH POD_OPENFOAM_VERSION=v2212 PYTHON=<conda>/bin/python3
    Solver_Examples/PODFoam/validation/run_v2106.sh'      # $POD_WORKSPACE/pod-v2212.XXXXXX에 씀
```

이미지는 호스트의 네트워크와 프로세스 이름공간을 함께 쓰므로, 이미지 안 솔버의 콜백이 호스트 GPU에 띄운
llama-server에 127.0.0.1로 닿습니다. `async_v2.slurm`은 서버(12B, 문맥 4096, batch와 ubatch 512, 그림
시험과 같은 설정)를 띄우고, 호스트에서 체크아웃의 git 상태를 기록하고(이미지에는 git이 없음. `pack_run.py`가
복사), 이미지 안에서 `POD_SUITE=async`와 `LLM_IMAGE_STYLE=v2`로 `run_demo.sh`를 돌린 뒤
`run_live_sweep.py`를 돌립니다.

```bash
# 저장소 최상위에서, 연결 검증 실행과 같은 격자의 발달한 실행이 있은 뒤
export POD_REFERENCE_RUN=<pod-v2212.XXXXXX> LLM_LONG_START=<developed case>/0.1
sbatch --account=<account> --partition=mb-a6000 Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
```

기본값: 시작 상태에서 5e-6 s 간격 6000걸음, 250걸음마다 저장, describe 요청은 250걸음, sequence 프레임은
3000·3250·3750걸음, 창 x 0~0.12 m, y 0~0.04 m, 그다음 500걸음마다 sweep 요청 열한 개(`SWEEP_STEPS`,
`SWEEP_PARALLEL`). `LLM_KILL_JOIN_S=0.2`: 이 노드에서는 0.5 GB 솔버에서 포크한 워커를 끊고 거두는 데 약
40 ms가 걸려 당시 기본값 0.02 s보다 깁니다(2026-10-27부터 기본 0.1 s). 발달한 상태는 같은 이미지의 `pimpleFoam`으로, 연결 검증 실행의
`fixed-pimple` 경우에서 `controlDict`만 바꿔 얻었습니다. 시간 간격을 스스로 맞추며(`maxCo 0.5`,
`maxDeltaT 5e-6`) 100 ms를 돌렸고 1 ms마다 저장했습니다(작업 24757429). 2026-10-22에 Slurm 작업
24757460으로 돌렸고, 결과는 [보고서](../../../../docs/results-20261022-live.md), 기록은
[근거](../../../../docs/evidence/2026-10-22-live-v2/README.md)에 있습니다.

이 노드에서는 타이밍 단위 시험 두 개(`test_image_rendered_when_request_disabled`,
`test_timeout_is_detected_by_polling`)가 같은 이유로 기본 `LLM_KILL_JOIN_S`에서 실패하고(이번 변경 전
코드도 마찬가지), `LLM_KILL_JOIN_S=0.2`에서는 통과합니다. `test_connection_refused_is_reported_without_a_stall`은
가끔 0.5 s 한도를 100분의 몇 초 넘깁니다.

## 2026-10-27 실행

MedicineBow에서 저장소 최상위 폴더에서, conda Python을 `PATH` 앞에 두고(시스템 `python3`에는 numpy가
없음) 소스에서 빌드한 llama-server가 쓰는 CUDA 모듈을 불러:

```bash
export PATH=<numpy가 있는 python 3>/bin:$PATH POD_LLM_RUNTIME=$PWD/llm-runtime-12b
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
# 변화 읽기 시험(sequence_test.py 묶음), Gemma와 Qwen
PICTURE_TEST_SET=<developed-sequence-test-20261027> PICTURE_TEST_SCRIPT=sequence_test.py \
  sbatch --export=ALL,MODELS="12b 26b 31b" --account=<account> --partition=mb-a30 \
  Solver_Examples/PODFoam/llm_demo/hpc/window_test.slurm
# 권장 이미지 토큰으로 4비트 Qwen
PICTURE_TEST_SET=<창 묶음> LLM_IMAGE_TOKENS=1024 LLM_IMAGE_MIN_TOKENS=1024 LLM_CTX=8192 \
  sbatch --export=ALL,MODELS="qwen3vl-32b-q4 qwen35-27b-q4 qwen35-35b-q4" --account=<account> \
  --partition=mb-l40s Solver_Examples/PODFoam/llm_demo/hpc/window_test.slurm
# 250걸음마다 describe 요청, 24,000걸음, 그리고 쌍둥이
POD_SUITE_RUN=<PASS한 async_v2.slurm 실행의 pod-llm-async.XXXXXX> \
  sbatch --account=<account> --partition=mb-a30 Solver_Examples/PODFoam/llm_demo/hpc/periodic_v2.slurm
```

작업 24903974~24903978(그림 시험), 24903264(주기 요청), 24903298과 24903263(`async_v2.slurm`으로 10월 22일
시험 반복. `POD_SUITE_RUN`을 주면 `async_v2.slurm`은 sweep만 돌리며, 작업 24903755가 그렇게 돌았음).
그림 시험의 첫 제출 가운데 시작한 두 개는 `window_test.slurm`이 CUDA 모듈을 더 이상 불러오지 않아 바로
멈췄고(`libcudart.so.12`를 못 찾음), 그래서 `POD_HOST_MODULES`를 넣었습니다. 결과는
[보고서](../../../../docs/results-20261027.md), 기록은 [그림 시험 근거](../../../../docs/evidence/2026-10-27-picture-tests/README.md)와
[솔버 근거](../../../../docs/evidence/2026-10-27-solver/README.md)에 있습니다.

## 시험한 곳

MedicineBow(와이오밍 대학교 ARCC), 2026-10-19, 쌍별 재생만:
`934da23`(영문 저장소)의 `replay_12b.slurm`, Slurm 작업 24696203, NVIDIA A30(24 GB) 한 장에서 35 s.
쓴 설정 줄([실제로 돌린 파일](../../../../docs/evidence/2026-10-19-12b/job/replay_12b.slurm)):

```bash
#SBATCH --account=<account>
#SBATCH --partition=mb-l40s,mb-a30
module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
export PATH=<python 3 with numpy>/bin:$PATH
```

미리 빌드된 b11429 CUDA 라이브러리는 GLIBC_2.38이 필요한데 MedicineBow는 2.34라서,
llama.cpp를 `build_llama_cuda.sh`로 소스에서 빌드했습니다(작업 24696057, 6분 22초;
[작업 스크립트](../../../../docs/evidence/2026-10-19-12b/runtime/build_llama.sbatch)):

```bash
#!/bin/bash
#SBATCH --partition=mb-a30,mb-l40s
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
export POD_LLM_RUNTIME=$PWD/llm-runtime-12b
export CMAKE_CUDA_ARCHITECTURES="80;89;90" BUILD_JOBS=16
export LDFLAGS="-L<cuda-toolkit>/lib64/stubs"
rm -rf "$POD_LLM_RUNTIME/llama.cpp-build"   # CMake는 처음 구성할 때만 LDFLAGS를 읽음
mv "$POD_LLM_RUNTIME/llama-b11429-cuda" "$POD_LLM_RUNTIME/llama-b11429-cuda.prebuilt" 2>/dev/null || true
bash Solver_Examples/PODFoam/llm_demo/hpc/build_llama_cuda.sh
```

stub 없이 CPU 노드에서 한 첫 빌드(작업 24695932)는 마지막 링크에서 `libcuda.so.1`을 찾지 못해
실패했습니다. 두 변경 중 어느 쪽이 고쳤는지는 따로 확인하지 않았습니다.

## 여기서 확인 못 한 것

`demo_12b.slurm`(GPU 노드에서 OpenFOAM v2106으로 도는 동기 시험. 비동기 시험은 대신 v2212 이미지에서
돌았음), 미리 빌드된 CUDA 바이너리,
`LLAMA_CUDA=13.4`, 12B 스크립트의 tar.gz 폴더 구조(같은 구조로 된 자기 묶음에서
`picture_test.slurm`이 2026-10-22에 돌았음).
`start_server.sh`는 10분 안에 `/health`가 안 뜨면 바로 실패하고, 로그는
`llm-runtime-12b/server-*.log`에 남습니다.
