# 10월 28일 근거: 기록을 쌓지 않는 콜백의 텔레메트리, 계산한 증감 단어

MedicineBow(와이오밍 대학교)의 Slurm 작업 24929555, CPU 파티션 `mb`, 노드 mbcpu-010, 코어 4개, 12분 15초:
OpenFOAM v2212(Apptainer 이미지 `of2212.sif`)의 PODFoam을 `main`(`2ed6da2`, [callback-main/](callback-main/python_module.py)에
복사)의 Python 콜백과 브랜치 `callback-telemetry-trends`(`16d665e`)의 Python 콜백으로, 같은 경우에서 같은
설정으로 돌렸습니다. 바뀐 점은
[llm_demo/README.md](../../../Solver_Examples/PODFoam/llm_demo/README.md#telemetryjsonl)에 설명되어 있습니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-28-callback/README.md)

## 무엇을 돌렸나

| 경우 | 콜백 | 요청 |
|---|---|---|
| `describe-main`, `describe-new` | main, 브랜치 | 걸음 100에서 describe |
| `sequence-main`, `sequence-new` | main, 브랜치 | 걸음 100, 150, 200의 프레임으로 sequence |
| `sequence-tn-new` | 브랜치 | 같은 sequence를 `LLM_SEQUENCE_PROMPT=tn`으로 |
| `par2-describe-main`, `par2-describe-new` | main, 브랜치 | 걸음 100에서 describe, MPI rank 2개(scotch) |

모든 경우: 작업 24757460에서 준비해 둔 계단 경우(`pod-llm-async.UM1RyJ/async-no-llm`: `0/`, `constant/`,
`system/`, 시작 상태 `0.1/`과 그 `pod_svd.py`), 곧 칸 20,540개에 발달한 흐름이 있는 2D 후향 계단; t = 0.1 s부터
5e-6 s 간격 1,250걸음; 필드와 POD 모드는 250걸음마다 저장; `LLM_ENABLED=0`(프레임을 그리고 요청 본문을 만들어
쓰지만, 아무것도 보내지 않음); `LLM_ASYNC=1`; `LLM_IMAGE_STYLE=v2`; 그린 창 x 0\~0.12 m, y 0\~0.04 m; BLAS
스레드 하나; main과 브랜치에 같은 `LLM_RUN_ID`(`callback-check/<경우>`). 다른 콜백 모듈은 브랜치의 것이고,
main의 것과 같습니다. PODFoam은 브랜치에서(그 C++는 main과 같음) `validation/run_v2106.sh`로 빌드했고, 연결
검증을 통과했습니다. rank 2개 경우는 10월 27일 MPI 시험처럼 자기 `pod_svd.py`의 rank 확인을 바꿨습니다. 작업은
[callback_check.sbatch](callback_check.sbatch)입니다.

## 결과

| 확인 | 결과 |
|---|---|
| 파일, describe 쌍 | 저장한 시각 폴더의 파일 105개, 프레임 파일 4개, 요청 본문, `python_svd_audit.npz`, `telemetry.jsonl`, 입력 파일 26개가 같음; 한쪽 실행에만 있는 파일 없음, 다른 파일 없음 |
| 파일, sequence 쌍 | 같음, 프레임 파일은 12개 |
| 파일, rank 2개 쌍 | processor 폴더의 파일 234개, 프레임 파일 4개, 요청 본문, `telemetry.jsonl`, 입력 파일 26개가 같음; `python_svd_audit.npz`는 비교하지 않음(아래) |
| `telemetry.jsonl` | 모든 실행에서 1,250줄, 세 쌍 모두 main과 브랜치가 같음; `telemetry.jsonl.tmp`가 남지 않음. 브랜치는 네 실행 모두에서 `PYTHON LLM telemetry lines=1250 appends=3 failed_appends=0 file=telemetry.jsonl`을 찍음 |
| 솔버 로그 | 직렬 쌍마다 솔버 줄 18,761개(잔차, Courant 수, 연속 오차, 시간, POD 스냅샷과 SVD 줄)가 순서까지 같음; rank 2개 쌍의 20,016줄은 정렬한 목록으로 같음(순서로는 같지 않음) |
| 기록 | `llm_request.json`, `llm_response.json`, `llm_result.json`은 타임스탬프, 프로세스 번호, 벽시계 시간, 도착 걸음, 파이프 집계만 다름; 브랜치는 sequence 실행의 `llm_result.json`과 `llm_response.json`에 `computed_trends`를 더하고, `llm_request.json`에는 더하지 않음 |
| 계산한 증감(`sequence-new`) | `increasing`(가장 큰 \|U\| 37.21에서 38.14 m/s로, +2.44 %), `more_negative`(가장 낮은 p −335.04에서 −376.20 m²/s²로, −10.9 %), `moves`(그린 범위의 6.92 %); 세 프레임의 `snapshot_runner.sequence_truth`와 같음. `computed_trends_agreement` 없음: 답한 모델이 없음 |
| `tn` 형태(`sequence-tn-new`) | 본문(667,051바이트)이 그 프레임들의 `readable_request.sequence_v2_payload(..., thresholds=True, numbers=...)`와 바이트까지 같음, 시스템 프롬프트는 `tn`; 프레임은 `sequence-new`의 것과 바이트까지 같음; 메모에는 37.2103, 38.0911, 38.1414 m/s와 −335.039, −367.852, −376.195 m²/s² |
| 기본 sequence 본문 | 2026-10-22 빌더(`own_ranges=True`, 다른 것 없음)를 프레임에 적용한 것과 같음 |
| 걸음당 콜백 벽시계 시간 | 중앙값이 main은 0.079\~0.107 ms, 브랜치는 0.163\~0.217 ms(브랜치는 걸음마다 그 줄을 솔버 프로세스에서 인코딩함); 걸음 500과 1,000(덧붙이기)은 브랜치에서 13.7\~22.0 ms; 마지막 걸음은 main 53\~57 ms, 브랜치 20\~23 ms(솔버 로그의 `POD analysis callback returned` 줄) |
| [memory.py](memory.py), 상태 24,000개 | 10월 27일 주기 실행에서 기록한 상태 24,000개 중 마지막 것 뒤의 Python 힙: main 31.685 MiB(상태당 1.351 KiB), 브랜치 0.067 MiB(최고 0.515 MiB); `telemetry.jsonl`을 쓰는 마지막 걸음: main 0.699 s, 브랜치 0.023 s; 다른 걸음의 중앙값 20 µs와 46 µs; 걸음 500, 1,000, 1,500(덧붙이기)은 9.1, 9.2, 11.6 ms, 마지막을 뺀 가장 느린 걸음은 16.6 ms(걸음 19,000, 덧붙이기); 두 버전 모두 기록된 파일(19,864,369바이트)을 바이트까지 똑같이 다시 씀. Python 3.11.16 |
| 단위 테스트 | 107개 통과(`test_llm_client test_callback test_ablation_runner test_async test_picture_test`) |
| 10월 22일 시험(`pod-llm-async.UM1RyJ`)에 브랜치의 `verify_async.py` | PASS |

비교는 두 번 돌았습니다. 작업 안에서 [compare.py](compare.py)는 rank 2개 쌍에 FAIL을 보고했습니다. 그 로그를
순서대로 비교하고 `python_svd_audit.npz`를 바이트로 비교했기 때문입니다. 두 차이 모두 콜백이 아니라 rank 두
개에서 옵니다. 두 프로세스가 로그 하나에 찍는 순서는 실행마다 바뀌고, 시험의 POD 모듈은 두 rank가 같은 경로에
같은 때 `python_svd_audit.npz`를 저장하게 해서 두 실행 모두 그 파일을 읽을 수 없습니다(zip CRC 오류).
compare.py를 병렬 로그는 정렬한 목록으로 비교하고 audit 파일은 비교하지 않고 기록만(읽을 수 있는지, 해시)
하도록 바꾼 뒤 같은 폴더에서 다시 돌렸습니다(Slurm 작업 24929607, mbcpu-006): PASS. 두 결과가 모두 여기
있습니다.

## 시험하지 않은 것

- 답한 모델이 없으므로(`LLM_ENABLED=0`) 이 실행들에는 `computed_trends_agreement`가 없습니다.
  `test_async.ComputedTrendTests`가 로컬 시험 서버로 이것을 확인합니다.
- 실패하거나, 강제로 종료되거나, 포기한 덧붙이기와 인코딩할 수 없는 상태는 솔버 실행이 아니라 단위 테스트에서만
  시험했습니다. 디스크 고장이나 가득 찬 디스크는 시험하지 않았습니다.
- 솔버 실행은 1,250걸음이었습니다. 24,000걸음 수치는 memory.py가 기록된 상태를 솔버 없이 재생한 결과입니다.
- 경우마다 CPU 노드 하나에서 실행 하나만 했습니다. 앞선 실행들의 GPU 노드에서 덧붙이기 시간은 재지
  않았습니다. rank는 2개만 해 봤습니다.
- `verify_async.py`의 새 확인(계산한 증감 단어, 그것과 모델 답의 일치, `t`와 `tn` 요청 형태)은 이 중 어느 것도
  없는 10월 22일 시험에서만 돌아서, 거기서는 기본 경로를 탔습니다. 위의 실행에서는 `compare.py`가 같은 내용을
  확인했습니다. `t` 형태와 동기 v2 sequence 경로는 단위 테스트에서만 돌았습니다.
- 근거 커밋 뒤의 단위 테스트: `237bcdf`에서 107개 OK(Slurm 24929611); `b63c990`에서 TMPDIR을 노드 로컬 디스크에
  두고(24929726), 그리고 NFS에 두고(24929736) 108개 OK. 그 출력은 여기 남기지 않았습니다.

## 파일

| 경로 | 내용 |
|---|---|
| `callback-main/python_module.py` | `2ed6da2`의 `main` 콜백, `-main` 경우에서 돌고 `test_callback.TelemetryTests`가 불러옴 |
| `callback_check.sbatch` | 작업 스크립트 |
| `compare.py`, `comparison.json` | 위의 비교(다시 돌린 것, 작업 24929607)와 그 결과 |
| `comparison-in-job.json` | 작업 안에서 compare.py의 첫 결과: 위에서 설명한 대로 rank 2개 쌍은 FAIL |
| `memory.py`, `memory.json` | 상태 24,000개 재생, 두 버전, tracemalloc이 있을 때와 없을 때 |
| `callback-check-24929555.out` | 작업 출력 |
| `validation.log` | 연결 검증 출력 |
| `unit-tests.log` | 작업 안의 단위 테스트 출력 |
| `verify-oct22-suite.json` | 10월 22일 시험에 대한 `verify_async.py`의 보고 |
| `sequence-new/llm_result.json`, `sequence-tn-new/llm_result.json` | `computed_trends`(와 `sequence_prompt`)가 있는 브랜치의 sequence 결과 |
| `describe-main/log.PODFoam.gz`, `describe-new/log.PODFoam.gz` | 직렬 describe 쌍의 솔버 로그(gzip 사본) |
| `HEAD`, `git-status.txt`, `changes.patch` | 작업이 시작할 때 작업 트리의 상태(변경 없음, `16d665e`) |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

## 참고

- 단위 테스트는 작업 끝에 작업 트리에서 돌았습니다. 그때 작업 트리에는 작업이 도는 동안 생긴 변경이 하나
  있었습니다(`test_async.py`의 예산 확인 허용 오차, 이 폴더와 함께 커밋함). 시험한 코드는 `16d665e`의
  것이었습니다.
- 모든 파일이 있는 실행 폴더(1.1 GB)는 클러스터에 남아 있습니다:
  `/cluster/medbow/gscratch/syome/github_repos/pod-callback-20261028/run-24929555`.
- 기록에는 출처를 보이려고 클러스터 경로와 프로세스 번호가 남아 있습니다.
