# GPU 노드에서 12B 모델 돌리기

E2B로 잰 것을 Gemma 4 12B QAT Q4_0으로 클러스터 GPU에서 다시 재는 스크립트입니다.
솔버 코드, 프롬프트, 시드, 저장한 상태는 2026-10-17에 쓴 그대로이고 모델과
컴퓨터만 바뀝니다.

| 스크립트 | 하는 일 |
|---|---|
| `setup_12b.sh` | llama.cpp b11429 CUDA 빌드와 12B 가중치·이미지 프로젝터를 `google/gemma-4-12B-it-qat-q4_0-gguf`에서 내려받고 SHA-256을 기록. 약 8 GB. |
| `start_server.sh` / `stop_server.sh` | 노드 GPU에서 llama-server를 E2B와 같은 설정(문맥 2048, 슬롯 1, 이미지 토큰 256, reasoning off)으로 띄움. 모든 층을 GPU에. `server.pid` 기록. |
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
2. `.slurm` 파일의 `module load` 줄을 클러스터에 맞게 고침 (CUDA 12.8 또는 13.4,
   numpy 있는 Python 3; demo는 matplotlib과 OpenFOAM v2106도 필요).
   노드 드라이버가 12.8을 못 받으면 `LLAMA_CUDA=13.4`.
3. 파티션과 `--gres` 표기가 클러스터와 맞는지 확인.

## 제출

```bash
# 저장소 루트(또는 tar.gz를 푼 루트)에서
export HF_TOKEN=hf_...
sbatch Solver_Examples/PODFoam/llm_demo/hpc/replay_12b.slurm   # GPU 1장, 한 시간 안
sbatch Solver_Examples/PODFoam/llm_demo/hpc/demo_12b.slurm     # OpenFOAM v2106이 있을 때만
# tar.gz를 풀었으면 경로는 PODFoam/llm_demo/hpc/...
```

결과는 `results/`에 생김: `replay-12b-<jobid>.tar.gz`(요청 6개, 답, `summary.json`,
`manifest.json`, GPU 이름, 런타임 manifest)와 `demo-12b-<jobid>.tar.gz`(검증 JSON,
시간, `run-archive.tar.gz`, 새 상태의 재생).

## 무엇을 비교하나

- 재생: `summary.json`의 `numeric_only`와 `numeric_plus_image`, 위치 오차는
  `ground_truth.private.json` 기준(참값 x = 0.000538 m, y = 0.01271 m).
  이 상태에서 E2B는 60.92 cm와 50.97 cm였음.
- demo: `timings.json`의 조건별 `cpp_measured_full_callback_s`
  (CPU의 E2B: 0.49 / 78.26 / 39.67 / 0.51 / 4.01 s), `demo-verification.json`의
  `status`가 `PASS`이고 같은 파일 45개.
- 각 결과의 `server_timings.cache_n`: 1이면 프롬프트 캐시가 비어 있었다는 뜻.

## 여기서 확인 못 한 것

CUDA 빌드와 12B 프로젝터는 이 노트북(GPU 없음)에서 돌려 보지 못했습니다.
`start_server.sh`는 10분 안에 `/health`가 안 뜨면 바로 실패하고, 로그는
`llm-runtime-12b/server-*.log`에 남습니다.
