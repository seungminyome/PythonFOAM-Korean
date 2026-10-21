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

`demo_12b.slurm`(MedicineBow에는 OpenFOAM 모듈이 없음), 미리 빌드된 CUDA 바이너리,
`LLAMA_CUDA=13.4`, L40S 파티션, tar.gz 폴더 구조.
`start_server.sh`는 10분 안에 `/health`가 안 뜨면 바로 실패하고, 로그는
`llm-runtime-12b/server-*.log`에 남습니다.
