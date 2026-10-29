# 10월 28일 근거: 동시에 진행 중인 요청 두 개

MedicineBow의 Slurm 작업 24929296, 2026-10-28, 16:42~16:55 MDT, 노드 mbl40s-001(NVIDIA L40S)입니다. OpenFOAM
v2212(Apptainer 이미지)의 PODFoam에서 50걸음마다 v2 describe 요청을 보내고 대기 중인 요청을 최대 두 개로
두어(`LLM_ANALYSIS_EVERY=50`, `LLM_ASYNC_MAX_PENDING=2`), 발달한 흐름의 t = 0.1 s부터 5e-6 s 간격으로
6,000걸음을 돌렸고, 요청 없는 같은 실행도 돌렸습니다. Gemma 4 12B QAT는 llama.cpp b11429 서버에서 슬롯 두
개로 돌렸습니다(`--parallel 2`, 문맥 8192, 슬롯마다 4096). 코드: `2ed6da2`의 체크아웃(`git/HEAD`, 변경 없음),
`hpc/periodic_v2.slurm`으로 실행:

```bash
POD_SUITE_RUN=<pod-llm-async.UM1RyJ of Slurm 24757460> PERIODIC_STEPS=6000 PERIODIC_FIRST=50 \
  PERIODIC_EVERY=50 PERIODIC_WRITE=50 PERIODIC_MAX_PENDING=2 LLM_PARALLEL=2 LLM_CTX=8192 \
  sbatch --account=<account> --partition=mb-a30,mb-l40s,mb-a6000 Solver_Examples/PODFoam/llm_demo/hpc/periodic_v2.slurm
```

[보고서](../../results-20261028.md) · [요청 하나만 대기하는 실행](../2026-10-27-solver/README.md)

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-28-inflight/README.md)

## 결과

[inflight.py](inflight.py)([inflight.json](inflight.json))로, 10월 27일에 250걸음마다 요청을 하나씩 보내고
대기 중인 요청을 최대 하나로 둔 실행(Slurm 24903264, NVIDIA A30 노드)과 비교한 것입니다:

| | 동시에 두 개, 50걸음마다 | 동시에 하나, 250걸음마다 |
|---|---:|---:|
| 계획한 요청 / 답한 요청 | 120 / 118 | 96 / 96 |
| 한도에 닿아 건너뜀 | 2 | 0 |
| 다른 요청이 대기 중일 때 보냄 | 112 | 0 |
| 요청 없는 실행과 같은 저장 파일 | 2,520개 중 2,520개 | 2,016개 중 2,016개 |
| 걸음당 벽시계 시간, 요청 없음 / 있음 | 0.06165 / 0.06363 s (+3.2 %) | 0.05794 / 0.05833 s (+0.7 %) |
| 답한 요청 하나당 더 든 벽시계 시간 | 0.101 s | 0.097 s |
| 요청 걸음에서 콜백 시간, 최대(마지막 걸음 제외) | 0.046 s | 0.017 s |
| 답이 온 때(마지막 요청 제외) | 50~111걸음 뒤 | 85~144걸음 뒤 |
| 모델 시간, 최소 / 중앙값 / 최대 | 2.54 / 3.80 / 4.65 s | 4.15 / 4.73 / 5.25 s |
| 가장 빠른 곳이 10 % 안(고정 답) | 117개 중 81개(62) | 96개 중 65개(53) |
| 가장 낮은 압력이 10 % 안(고정 답) | 117개 중 106개(78) | 96개 중 89개(65) |

- 서버 슬롯이 두 개여서 콜백은 요청 두 개를 계속 진행시켰습니다. 답한 요청 118개 중 112개는 앞의 요청이
  아직 대기 중일 때 보냈고, 대기 중인 요청 두 개를 만난 두 걸음(4150과 5550)은 설계대로 건너뛰고
  기록했습니다.
- 요청이 다섯 배 많았는데 벽시계 시간은 3.2 % 더 들었습니다. 요청 하나당 더 든 시간은 두 실행 모두 약
  0.1 s입니다. 요청 없는 두 실행도 같은 그림을 그렸으므로, 이것은 그리기 위에 얹힌 요청의 비용입니다. 두
  비교 모두 실행 한 쌍씩이고, 서로 다른 노드에서 돌았습니다.
- 답한 요청 하나에 결과 파일이 없습니다. 걸음 4100의 요청에 대한 답은 걸음 4167에 도착했지만
  (`index.json`: 상태 ok, 모델 시간 3.0 s), [step-004100/](step-004100/)의 기록에는 요청, 답, 응답 기록만 있고
  `llm_result.json`이 없으며, 로그에도 그 결과 줄이 없습니다. 콜백은 이 파일들을 fork한 writer에서 쓰는데,
  솔버가 그보다 오래 기다리지 않도록 writer를 0.2 s 뒤에 멈추고, 그 걸음은 0.207 s 걸렸습니다. 솔버는 영향을
  받지 않았습니다. `run_periodic.py`는 이 기록에서 요약을 만들다 멈췄습니다. 여기 있는
  `periodic-summary.json`은 `c85c79c`의 `run_periodic.py --summary-only`로 다시 만든 것으로, 이 버전은 그런
  요청을 `records_missing`에 적고 점수에서 뺍니다(점수를 매긴 것 117개).

## 파일

| 경로 | 내용 |
|---|---|
| `periodic-summary.json` | 계획, 요청마다(걸음, 상태, 도착 걸음, 모델 시간, 솔버 대기, 바이트, 일치 확인, 점수, 해석한 답), 쌍둥이와의 파일 비교, 시간, 메모리; 위처럼 다시 만듦 |
| `timings.json`, `resident-server.json` | 두 경우의 벽시계 시간과 메모리 최고값; 실행이 쓴 서버 |
| `periodic-describe/llm_requests/index.json` | 요청 걸음 120개에 대한 콜백의 목록 |
| `<경우>/log.PODFoam.gz`, `telemetry.jsonl.gz`, `memory-samples.json.gz`, `timeline.json.gz` | 두 경우의 솔버 로그, 걸음별 텔레메트리, 메모리 측정, 콜백의 로그 줄(gzip 사본) |
| `step-004100/` | 결과 파일이 쓰이지 않은 요청의 기록 |
| `pod-periodic-v2-24929296.out`, `periodic.log` | 작업 출력과 실행기의 출력(KeyError에서 끝남) |
| `server-*.cmd`, `server-*.log.gz`, `models-*.json`, `gpu-*.txt`, `gpu-samples.csv.gz`, `nvidia-smi.txt`, `runtime_manifest_12b.json` | 서버 명령줄(슬롯 두 개), 로그, 모델 목록, GPU 메모리, 1초마다 GPU 측정, 12B 파일 해시 |
| `git/`, `executed-callback-source.sha256` | 작업 시작 때의 코드 상태와 실행된 콜백 파일의 해시 |
| [inflight.py](inflight.py), [inflight.json](inflight.json) | 위의 비교 |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

모든 요청의 요청 본문, 답, 프레임과 시각 폴더를 뺀 경우들은
[tests-2026-10-28](https://github.com/seungminyome/PythonFOAM/releases/tag/tests-2026-10-28)
릴리스의 `inflight-24929296.tar.gz`에 있습니다. 기록에는 출처를 보이려고 클러스터 경로와 프로세스 번호가 남아
있습니다.
