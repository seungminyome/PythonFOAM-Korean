# 10월 27일 근거: 250걸음마다 요청, 반복 실행, MPI, POD 파일, 불안정 흐름 시도

MedicineBow(와이오밍 대학교)에서 2026-10-27에 돌린 솔버 실행입니다. PODFoam은 OpenFOAM v2212(Apptainer
이미지 `of2212.sif`)에서, Gemma 4 12B QAT는 노드 mba30-005의 GPU(NVIDIA A30)에서 돌렸고, CPU 작업도 있습니다.
같은 날의 그림 시험은 [2026-10-27-picture-tests](../2026-10-27-picture-tests/README.md)에 있습니다.

[보고서](../../results-20261027.md) ·
[모든 압축 파일이 있는 릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/tests-2026-10-27) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-27-solver/README.md)

## 작업

| 작업 | 내용 | 어디서 | 시각(MDT) |
|---|---|---|---|
| 24903264 | t = 0.1 s부터 5e-6 s 간격 24,000걸음, 250걸음마다 describe 요청(요청 96개), 그리고 요청 없는 같은 실행 | A30, mba30-005 | 08:49~09:37 |
| 24903298 | 10월 22일 시험(비동기 경우 다섯 개)과 요청 열한 개 sweep의 반복 1 | A30, mba30-005 | 08:51~09:41 |
| 24903263, 24903755 | 반복 2: 시험(24903263), 이어서 sweep만(24903755) | A30, mba30-005 | 08:46~09:41 |
| 24903786 | MPI rank 2개에서 관찰 기능, 직렬 실행과 비교(600걸음, 100걸음에 프레임, 모델 없음) | CPU, mbcpu-001 | 09:26~09:28 |
| 24903065 | 짝지어 돌린 실행에서 POD 모드 파일이 왜 달랐나: 600걸음 실행 여섯 개 | CPU, mbcpu-001 | 08:47~08:52 |
| 24903082, 24903162, 24903182 | 불안정한 흐름 만들기 시도: 더 큰 시간 간격과 중심 차분으로 `pimpleFoam` | CPU | 08:28~08:40 |

## 이 폴더의 결과

| 폴더 | 결과 |
|---|---|
| [periodic/](periodic/) | 요청 96개 중 96개 답함; 저장 파일 2,016개 모두 요청 없는 실행과 같음; 걸음당 벽시계 시간 0.05833 s 대 0.05794 s(+0.7 %; 요청 없는 실행도 같은 그림을 그림; 실행 한 쌍, 노드에 다른 작업이 함께 돎); 콜백이 요청 걸음에서 쓴 시간은 최대 0.017 s(마지막 걸음은 설계대로 대기 중인 답을 기다림, 6.8 s); 요청마다 파이프로 돌아온 바이트 4,009~4,461; 가장 빠른 곳이 10 % 안인 답 96개 중 65개(고정 답: 53), 가장 낮은 압력 96개 중 89개(고정 답: 65). [tracking.py](periodic/tracking.py): 답한 x가 참 x를 따라가는 상관계수는 가장 낮은 압력 0.78, 가장 빠른 곳 0.35([tracking.png](periodic/tracking.png)). [misses.py](periodic/misses.py): 가장 빠른 곳을 틀린 31개 중 27개는 최고 속력의 90 % 이상인 곳을, 가장 낮은 압력을 틀린 7개 중 5개는 최저 압력의 90 % 이상인 곳을 짚음. [memory.py](periodic/memory.py): 250걸음 주기마다 가장 낮을 때 솔버 프로세스는 요청 없이 85 MiB, 요청과 함께 70 MiB 늘고, 그중 32 MiB는 콜백이 걸음마다 쌓는 기록 |
| [repeats/](repeats/) | 두 반복 모두 PASS; sweep의 POD 모드 파일 말고는 모든 저장 필드가 첫 실행과 같음; 요청 본문 13개가 첫 실행과 같음; 답 13개는 두 반복끼리 같고, 첫 실행(A6000)과 모든 항목까지 같은 답은 없음; sweep에서 10 % 안인 수는 첫 실행처럼 11개 중 9개와 10개([compare-repeats.py](repeats/compare-repeats.py)) |
| [mpi/](mpi/) | rank 2개: 두 프레임 모두 칸 20,540개, 칸 중심은 4e-17 m까지 같음, U는 직렬 프레임과 7.5e-4 m/s(37.2 중) 안, p는 0.021 m²/s²(335 중) 안 |
| [poddiff/](poddiff/) | BLAS 스레드 8개로 돌리면 POD 모드 파일 30개가 모두, 혼자 돌든 짝지어 돌든, 스레드 하나로 돈 실행과 최대 1.0e-13만큼 다르고(그 파일의 최댓값 0.098이므로 상대로 약 1e-12), 나머지 저장 파일 12개(흐름 필드)는 같음; 스레드 하나면 짝지어 돌아도 파일 42개가 모두 같음([mode_differences.py](poddiff/mode_differences.py)) |
| [unstable/](unstable/) | 시도 아홉 개([unstable-summary.json](unstable/unstable-summary.json)): 풍상(upwind) 대류는 시험한 모든 시간 간격에서 끝까지 돎(최대 Courant 수 28까지); 중심 차분은 Courant 수 4.5와 11에서 첫 걸음에 부동소수점 예외로 멈추고, 1.54 이하에서는 끝까지 돎 |

## 파일

| 경로 | 내용 |
|---|---|
| `periodic/periodic-summary.json` | `run_periodic.py`의 요약: 계획, 요청마다(걸음, 상태, 도착 걸음, 모델 시간, 솔버 대기, 바이트, 일치 확인, 점수, 해석한 답), 쌍둥이와의 파일 비교, 시간, 메모리 |
| `periodic/periodic-describe/llm_requests/index.json` | 요청 기록 96개에 대한 콜백의 목록(본문과 프레임이 있는 기록 자체는 릴리스에 있음) |
| `periodic/<경우>/log.PODFoam.gz`, `telemetry.jsonl.gz`, `memory-samples.json.gz`, `timeline.json.gz` | 두 경우의 솔버 로그, 걸음별 텔레메트리, 메모리 측정, 콜백이 쓴 줄의 시간 기록(gzip 사본) |
| `periodic/memory.py`, `memory.json` | 250걸음 주기마다 가장 낮을 때의 솔버 메모리(주기 안에서는 POD 모듈의 스냅샷 때문에 오르내림), 요청이 있을 때와 없을 때, 그리고 콜백이 걸음마다 쌓는 기록의 크기; `<경우>/memory-samples.json.gz`와 `timeline.json.gz`를 읽음 |
| `periodic/misses.py`, `misses.json` | 10 % 넘게 틀린 답마다, 짚은 칸의 속력이나 압력을 참 극값에 대한 비로; 릴리스 압축 파일(`periodic-24903264.tar.gz`)에 있는 `periodic-describe`의 프레임이 필요함 |
| `periodic/` 나머지 파일 | 작업 출력과 실행 로그, 서버 명령, 로그, 모델 목록, GPU 측정, 콜백 원본의 해시, 코드 상태(HEAD, 상태, 패치) |
| `repeats/<작업>/` | 검증, 요약, 시간, 빌드 입력, 코드 상태, 시험의 모든 파일 해시 목록(`sha256.json.gz`), describe와 sequence 결과, sweep 요약, sweep 결과 열한 개와 sweep의 모든 파일 해시 목록; 작업 출력과 서버 파일 |
| `repeats/run1-sweep-sha256.json.gz` | 첫 실행 sweep의 해시 목록. 그 압축 파일(pod-insitu-v2-2026-10-22 릴리스의 `sweep-UM1RyJ.tar.gz`)에서 [hash_tree.py](repeats/hash_tree.py)로 만듦 |
| `repeats/compare-repeats.py`, `.json` | 위의 비교. 이 폴더와 [../2026-10-22-live-v2/](../2026-10-22-live-v2/README.md)의 파일로 계산 |
| `mpi/` | 작업 스크립트와 출력, 프레임 비교, 연결 검증 로그, 두 솔버 로그(gzip), 분할 설정과 로그, 코드 상태 |
| `poddiff/` | 작업 스크립트와 출력, 저장 파일 전부를 실행 A와 해시로 비교한 결과, 차이의 크기 |
| `unstable/` | 작업 스크립트, 출력, 요약 스크립트와 그 결과 |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

## 참고

- 돌린 코드(커밋은 영문 저장소의 것). 주기 실행과 두 반복: Python 콜백은 `df72c24`와 같습니다(콜백 파일 여섯 개
  모두; `pod_svd.py`는 경우 자체의 모듈). 두 반복은 PODFoam을 `df72c24`와 같은 원본으로 컴파일했는데,
  `PythonCreate.H`와 `PythonGather.H`만은 이 빌드 뒤에 병렬 수정(`globalPath`, `scatterList`)이 들어갔습니다.
  실행은 직렬입니다. 주기 실행은 10월 22일 실행(Slurm 24757460)의 PODFoam 바이너리를 썼습니다. MPI 시험:
  컴파일한 원본이 모두 `df72c24`와 같습니다. 작업마다 본 코드 상태는 그 `HEAD`, `git-status.txt`,
  `changes.patch`에 있습니다.
- 반복 1(24903298)과 반복 2(24903263)는 시험이 통과한 뒤 종료 코드 1로 끝났습니다. 반복 1: 빌드 뒤에 원본
  폴더의 `PythonCreate.H`가 바뀌어서 `pack_run.py`가 묶기를 거부했습니다. 압축 파일은 나중에, 바뀐 파일을
  거부하지 않고 기록하는 `ab6b943`의 `pack_run.py`로 만들었습니다(`build-inputs.json`의
  `source_tree_changed_since_build`). 반복 2: sweep이 `window_test.py`의 문법 오류(`df72c24`에서 고침)에서
  멈췄고, 작업 24903755가 sweep만 돌렸습니다. 그 전의 반복 1(24903262)은 컴파일에서 멈췄고
  (`pythonGatherToMaster`가 선언되지 않음), 남기지 않았습니다.
- POD 차이 작업: `comparison.json`을 쓴 뒤 스크립트 마지막 줄(`set -e` 아래에서 실행마다 걸음 수를 세는 줄)에서
  종료 코드 1로 끝났습니다. 실행마다 exit 0을 찍었습니다.
- 두 반복과 주기 실행의 시각 폴더는 릴리스에 넣지 않았습니다. 반복의 시각 폴더가 첫 실행의 것과 같음은 여기의
  해시 목록이, 주기 실행의 시각 폴더가 쌍둥이의 것과 같음은 주기 실행의 바이트 비교(`periodic-summary.json`:
  같음 2,016개, 다름 0개)가 보여 줍니다.
- MPI 시험: 경우의 POD 모듈 `pod_svd.py`는 rank 0이 아니면 거부합니다. 시험은 자기 사본에서만 그 확인을
  바꿨습니다(`mpi_test.sbatch` 참고).
- 기록에는 출처를 보이려고 클러스터 경로와 프로세스 번호가 남아 있습니다.
