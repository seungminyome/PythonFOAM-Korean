# GPU 경로: Slurm GPU 노드에서 Gemma 4 12B 실행

이 스크립트들은 관찰 예제의 비동기 시험 묶음을 v2 이미지와 Gemma 4 12B로 GPU 노드 하나에서
실행합니다. OpenFOAM은 Apptainer 이미지 안에서 실행됩니다. llama-server는 호스트 GPU에서
실행되고, 콜백은 127.0.0.1로 서버에 접속합니다.

| 스크립트 | 하는 일 |
|---|---|
| `setup_12b.sh` | llama.cpp b11429의 CUDA 빌드, 12B 가중치, 이미지 프로젝터를 `POD_LLM_RUNTIME`에 내려받고 SHA-256을 확인합니다. 모두 약 8 GB입니다. 이 파일들과 그 폴더의 `llama-server`의 SHA-256을 기록하고, 그 서버가 실행되는지도 기록합니다. |
| `build_llama_cuda.sh` | llama.cpp b11429를 소스에서 CUDA로 같은 폴더에 빌드합니다. |
| `start_server.sh` | 노드의 GPU에서 모든 층을 올린 `llama-server`를 시작하고, `server.pid`를 쓰고, 최대 10분 동안 `/health`를 기다립니다. |
| `stop_server.sh` | `server.pid`에 적힌 서버를 멈춥니다. |
| `async_v2.slurm` | 배치 작업입니다. 서버를 시작하고, 이미지 안에서 `run_demo.sh`를 `POD_SUITE=async`, `LLM_IMAGE_STYLE=v2`로 실행하고, 서버를 멈춥니다. |

## 필요한 것

- `POD_LLM_RUNTIME`: 가중치와 `llama-server`를 둘 폴더입니다. 작업의 기본값은 출력처럼
  저장소 옆의 `../llm-runtime-12b`입니다.
- 가중치에는 Gemma 라이선스가 적용됩니다. Hugging Face의
  `google/gemma-4-12B-it-qat-q4_0-gguf`를 보십시오. `HF_TOKEN`을 설정하면 내려받을 때 함께
  보냅니다. 공개 저장소에는 토큰이 필요 없고, 이미 받아 둔 가중치에도 필요 없습니다.
- `SIF`: 컴파일러를 갖춘 OpenFOAM 이미지입니다. 예를 들어
  `apptainer pull docker://opencfd/openfoam-dev:2212`로 받습니다. `OPENFOAM_BASHRC`는 이미지
  안의 bashrc이고, `POD_OPENFOAM_VERSION`은 그 bashrc가 알리는 버전입니다. 기본값은
  `/usr/lib/openfoam/openfoam2212/etc/bashrc`와 `v2212`입니다. 이 예제의 이전 판으로 두 값을
  정해 같은 작업을 v2012와 OpenFOAM 8 이미지에서도 실행했습니다. 아래의 `POD_REFERENCE_RUN`과
  `LLM_LONG_START`는 작업이 쓰는 이미지에서 만든 것이어야 합니다.
- `PYTHON`: 이미지에서 보이는 Python 3.10\~3.12이며 numpy와 matplotlib이 있어야 합니다.
- `POD_REFERENCE_RUN`: 기준 실행입니다. 그 이미지에서 통과한 검증 실행이어야 합니다.
- `LLM_LONG_START`: 같은 격자로 발달시킨 유동 실행의 숫자 시간 폴더이며, 옆에
  `constant/polyMesh`가 있어야 합니다. 격자 파일 다섯 개는 파일 머리글까지 기준 실행과
  바이트 단위로 같아야 합니다. 다른 OpenFOAM 버전이 쓴 격자는 거부될 수 있습니다. 실행 중
  최대 Courant 수는 1보다 작아야 합니다. 그 검증 실행의 `fixed-pimple` 복사본을
  `pimpleFoam`으로 이어 돌리면 그런 상태를 얻을 수 있겠지만, 시도하지 않았습니다.
- 선택: `POD_HOST_MODULES`는 소스에서 빌드한 `llama-server`가 필요로 하는 호스트 모듈입니다.
  없으면 서버가 `libcudart.so.12`를 찾지 못해 시작할 때 멈춥니다.

미리 빌드된 CUDA 실행 파일은 GLIBC_2.38과 GLIBCXX_3.4.32, 곧 glibc 2.38과 GCC 13의
libstdc++가 필요합니다. glibc 2.34에서는 실행되지 않습니다. 그런 시스템에서는
`build_llama_cuda.sh`로 llama.cpp를 빌드합니다. cmake, C++17 컴파일러, CUDA 툴킷이 필요하며,
`llama.cpp-src`가 아직 없으면 git과 인터넷 접속도 필요합니다.

툴킷의 `lib64/stubs`를 `LDFLAGS`에 넣은 GPU 노드의 빌드는 성공했고, stubs 없이 CPU 노드에서
한 빌드는 실패했습니다. CMake는 처음 구성할 때만 `LDFLAGS`를 읽습니다. 성공한 빌드는 아래
명령처럼 미리 빌드된 폴더를 먼저 옆으로 옮겼습니다. 그러지 않으면 그 라이브러리가
`LD_LIBRARY_PATH`에 남습니다. 빌드한 뒤에는 `setup_12b.sh`를 다시 실행해 `sha256.txt`와
매니페스트가 빌드한 서버를 가리키게 합니다.

폴더의 `llama-server`가 실행되지 않으면 `setup_12b.sh`는 로더의 메시지를 출력하고
매니페스트에 `"server_runs": false`를 씁니다. 내려받은 파일은 그래도 온전합니다.

## 명령

저장소 최상위에서:

```bash
export POD_LLM_RUNTIME=$PWD/../llm-runtime-12b PYTHON=<python>
bash Solver_Examples/PODFoam/llm_demo/hpc/setup_12b.sh     # once, where there is internet

# if the prebuilt binaries do not run, in a GPU job
module load <modules>
mv "$POD_LLM_RUNTIME/llama-b11429-cuda" "$POD_LLM_RUNTIME/llama-b11429-cuda.prebuilt"
LDFLAGS="-L<cuda-toolkit>/lib64/stubs" bash Solver_Examples/PODFoam/llm_demo/hpc/build_llama_cuda.sh
bash Solver_Examples/PODFoam/llm_demo/hpc/setup_12b.sh

# the reference run, in the image, on a node with apptainer
export OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212
apptainer exec <image> bash -c 'source "$OPENFOAM_BASHRC"
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd Solver_Examples/PODFoam && ./validation/run.sh'

# the job
export POD_LLM_RUNTIME=$PWD/../llm-runtime-12b PYTHON=<python>
export SIF=<image> POD_HOST_MODULES="<modules>"
export POD_REFERENCE_RUN=<pod-v2212.XXXXXX> LLM_LONG_START=<developed case>/<time>
sbatch --account=<account> --partition=<partition> Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
```

작업은 다음 값을 씁니다.

| 설정 | 작업의 값 |
|---|---|
| 단계 | 5e-6초 단계 6000개, 250단계마다 저장 |
| `describe` 요청 | 250단계 |
| 시퀀스 프레임 | 3000, 3250, 3750단계 |
| 표시 영역 | x 0\~0.12 m, y 0\~0.04 m |
| 서버 컨텍스트 | 4096 |
| batch와 ubatch | 512 |
| `LLM_TIMEOUT_S`, `LLM_MAX_TOKENS` | 120, 320 |
| `LLM_IMAGE_STYLE`, `POD_SUITE` | `v2`, `async` |
| 엔드포인트 | `POD_LLM_PORT`에서 |
| `LLM_KILL_JOIN_S` | 따로 주지 않으면 0.2 |

`LLM_LONG_*`, `LLM_IMAGE_XRANGE`, `LLM_IMAGE_YRANGE`는 앞의 네 줄을 바꿉니다. 나머지는 작업이
고정하며, `LLM_KILL_JOIN_S`만 예외입니다.

더 짧은 실행에는 프레임을 따로 정해야 합니다. `LLM_LONG_STEPS=1000`이면
`LLM_LONG_SEQUENCE_STEPS=250,500,750`을 설정합니다. 기본 프레임은 1000단계 뒤에 있어서 시퀀스
요청이 나가지 않습니다.

`start_server.sh`는 `LLM_MODEL_FILE`, `LLM_PROJECTOR_FILE`, `LLM_PARALLEL`, `LLM_THREADS`,
`LLM_GPU_LAYERS`, `LLM_IMAGE_TOKENS`, `LLM_IMAGE_MIN_TOKENS`도 읽습니다. 작업이 아니라 직접
부르면 `LLM_CTX`, `LLM_BATCH`, `LLM_UBATCH`도 읽습니다. `setup_12b.sh`는 `LLAMA_CUDA`와
`GEMMA_12B_REVISION`을 읽습니다. 고정된 리비전의 가중치와 프로젝터, CUDA 12.8 압축 파일의
SHA-256을 확인합니다. 다른 리비전이나 다른 CUDA 빌드는 해시를 기록만 합니다.
`build_llama_cuda.sh`는 `CMAKE_CUDA_ARCHITECTURES`와 `BUILD_JOBS`를 읽습니다.

## 나오는 것

모두 `POD_ASYNC_OUT`에 들어갑니다. 기본값은 저장소 옆의 `../pod-async-v2/run-<job>`입니다.

- `pod-llm-async.XXXXXX/`: 다섯 케이스, `async-verification.json`, `summary.json`,
  `run-archive.tar.gz`입니다. 압축 파일은 1000단계에서 약 500 MB입니다.
  [관찰 예제의 README](../README.md)가 이 파일들을 설명합니다.
- `suite.log`, 이미지·Python·모듈을 적은 `site.txt`, `nvidia-smi.txt`, `gpu-samples.csv`.
  Slurm 자체의 출력은 `llm_demo/`의 `pod-async-v2-<job>.out`이며 git이 무시합니다.
- `server/`: 서버의 로그와 명령줄.
- `git/`: 체크아웃의 HEAD, 상태, diff. `llm-demo-work/`: 빌드.

### 실행한 시험

`async_v2.slurm`은 12B와 소스에서 빌드한 서버로 A30에서 실행했고, 모든 검사를 통과했습니다.

| 실행 | 코드 | 버전 | 시간 |
|---|---|---|---|
| `LLM_LONG_STEPS=1000`, 프레임 250, 500, 750, 발달한 상태에서 시작 | 이 코드 | v2212 | |
| 같은 실행 | 이 예제의 이전 판 | v2012, OpenFOAM 8 | |
| 기본 6000단계, 한 번 | 이 예제의 이전 판 | v2212 | 31분, 케이스당 333초 |

위 명령 중 앞의 두 묶음에 있는 `bash` 명령 세 개는 2026-11-01에 `HF_TOKEN` 없이, 스크립트의
이전 판으로 적힌 대로 실행했습니다.

| 단계 | 결과 |
|---|---|
| 로그인 노드에서 `setup_12b.sh` | 47초. 그중 약 25초가 합쳐서 7.9 GB인 파일 네 개를 내려받는 데 들었습니다. 네 파일 모두 10월 19일 런타임과 SHA-256이 같습니다 |
| soname 링크가 없는 미리 빌드된 서버 | `libllama-common.so.0: cannot open shared object file`로 멈춥니다. `setup_12b.sh`는 링크를 남깁니다 |
| 링크가 있는 미리 빌드된 서버, GLIBC 2.34 노드 | `GLIBC_2.38' not found`로 멈춥니다 |
| A30 노드에서 `build_llama_cuda.sh` | 335초. 빌드한 서버가 모델을 5초에 올리고 텍스트 요청에 0.8초 만에 답했습니다 |

실행하지 않은 것이 두 가지 있습니다. GLIBC 2.38 시스템에서 미리 빌드된 CUDA 실행 파일, 그리고
`LLAMA_CUDA=13.4`입니다.
