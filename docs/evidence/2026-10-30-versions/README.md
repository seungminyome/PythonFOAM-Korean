# 10월 30일 근거: OpenFOAM 버전과 원본 PODFoam

2026-10-30 MedicineBow(와이오밍 대학교)의 Slurm 작업입니다. 관찰 기능을 넣은 PODFoam을 OpenFOAM v2012, v2106, v2212, 8에서
각각 Apptainer 이미지로 돌렸고, `6fde869`의 원본 PODFoam과 비교했습니다. 보고서는
[results-20261030.md](../../results-20261030.md)입니다.
[report_numbers.py](report_numbers.py)는 보고서의 수치를 여기 기록에서 읽어 [report-numbers.json](report-numbers.json)에 씁니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-30-versions/README.md)

## 코드

커밋 해시는 영문 저장소 기준입니다. 대부분의 작업은 `b17763d`를 돌렸습니다. PR 트리(브랜치 `pr/podfoam-observer`, 이전 README)의
로컬 커밋이며 GitHub에 없습니다. 코드는 `bf7a06e`, `main`과 같습니다.
[code-identity.txt](code-identity.txt)는 `Solver_Examples/PODFoam` 아래 파일 64개(README 세 개 제외)의 blob을 git 객체에서 읽어 적습니다.
그 폴더 아래에서 `b17763d`와 `bf7a06e`가 다른 파일은 `llm_demo/README.md`와 `llm_demo/hpc/README.md`뿐입니다.
`main`에만 있는 파일 24개(실험 스크립트, 그 테스트)도 거기에 있습니다. 단위 테스트 말고 여기 작업 중 이 파일들을 돌린 것은 없습니다.

작업 폴더마다 `HEAD`가 있고, `git-status.txt`를 기록한 작업에서는 모두 비어 있습니다.

## 실행한 것

| 폴더 | 작업 | 코드 | 실행한 것 | 결과 |
|---|---|---|---|---|
| `matrix/` | 24950780\~24950783 | `b17763d` | [version_check.sbatch](scripts/matrix/version_check.sbatch): 빌드와 연결 검증, 이어서 모델 없는 관찰 기능(`LLM_ENABLED=0`), 100단계의 v2 프레임, t = 0.1 s에서 110단계: `serial2d`, `serial3d`, `par2d`, `par3d` | [compare.out](compare.out), [version-compare.json](version-compare.json); 모두 PASS, 네 버전 모두 네 케이스가 끝까지 감 |
| `commits/` | 24950784\~24950791 | `2a93911`, `69cc2c1` | [try_version.sh](scripts/try_version.sh): PR 트리의 커밋 2와 3에서 검증 | 넷 모두 PASS |
| `stand-in/` | 24950794\~24950797 | `b17763d` | [suites.sbatch](scripts/stand-in/suites.sbatch): 검증, `run_demo.sh`의 시험 모음 둘과 v2 비동기 시험 모음, [stub_server.py](scripts/stand-in/stub_server.py) 상대로 | 모두 종료 코드 0과 `PASS` |
| `documented-commands/` | 24950840\~24950843 | `b17763d` | [doc_commands.sh](scripts/refix-jobs/doc_commands.sh): PR 트리 `llm_demo/README.md`의 관찰 기능 명령을 새 사본에서 | 파일 45개 중 45개 같음, `DOC COMMANDS PASS` |
| `quick-start-24950804/` | 24950804 | `b17763d` | [quick_steps.sh](scripts/refix-jobs/quick_steps.sh): PR 트리의 빠른 시작을 v2106 이미지에서 순서대로, CPU 8개의 Gemma 4 E2B. `setup_runtime.sh`는 E2B 파일이 이미 있어 아무것도 내려받지 않음 | [steps.tsv](quick-start-24950804/steps.tsv): 10개 중 10개 종료 코드 0, 시험 모음 둘 다 PASS |
| `gpu-suite-24950817/` | 24950816(기준), 24950817 | `b17763d` | [submit_suite.sh](scripts/gpu/submit_suite.sh): 고치지 않은 `async_v2.slurm`, v2212, Gemma 4 12B, NVIDIA A30, `LLM_LONG_STEPS=1000`, 250, 500, 750단계의 sequence 프레임 | `async-verification.json` PASS |
| `gpu-suite-24949283/` | 24949283 | `fae10ba` | 같은 실행을 `fae10ba`에서, NVIDIA L40S. 이 커밋의 `async_v2.slurm`과 코드는 `b17763d`와 다름 | `async-verification.json` PASS |
| `gpu-versions-24950818/` | 24950818 | `b17763d` | [part_a.sbatch](scripts/gpu/part_a.sbatch): 호스트 GPU에 서버 하나, 이미지를 차례로, 110단계 중 100단계에 실제 `describe` 요청 하나, NVIDIA A30 | `part-a.json`: 넷 모두 `ok` |
| `gpu-versions-24949167/` | 24949167 | `fae10ba` | 같은 실행을 NVIDIA L40S에서 | `part-a.json`: 넷 모두 `ok` |
| `docker-24950798/` | 24950798 | `b17763d` | [docker_inner.sh](scripts/refix-jobs/docker_inner.sh): 원본의 이미지 `romitmaulik1/pythonfoam_docker`(Ubuntu 18.04, OpenFOAM 8, Python 3.6.9): OpenFOAM만 source한 검증, `wclean && wmake`, 제공된 `Run_Case`를 120 s | PASS; 종료 코드 0; 1,349단계, 제한 시간에 멈춤 |
| `upstream-comparison/` | 24951136\~24951140 | `bf7a06e` | [pod_account.sbatch](scripts/matrix/pod_account.sbatch): 원본과 이 포크의 빌드, 원본 모듈, 차이마다 원인 확인 | 폴더마다 `account.json` |
| | 24951141 | `bf7a06e` | [upstream_regression.sbatch](scripts/matrix/upstream_regression.sbatch): `LESModel`을 넣은 제공된 `Run_Case`, v2106 | `regression.json`: 90단계 뒤 종료 코드 1, 87단계 뒤 종료 코드 136 |
| | 24950800\~24950803 | `2a93911` | 훅이 없는 PR 트리 커밋 2에서 같은 비교: 8의 제공된 케이스와 안정화한 케이스, v2106과 v2212의 안정화한 케이스 | 같은 수와 크기 |
| | 24948188\~24948191 | `adcaec7` | 같은 비교를 v2012, v2106, v2212에서, 회귀는 v2106에서. `adcaec7`의 C++는 `bf7a06e`와 다름 | 같은 수와 크기 |
| `schedule/` | 24950748, 24950749 | `ef78700` | [schedule.py](scripts/schedule/schedule.py): 적어 둔 규칙으로 예측한 표와 POD 일정 비교, 이 포크 20회와 원본 빌드 6회, v2106과 8; [scenarios.py](scripts/schedule/scenarios.py): 실패와 경계 케이스 46개 | `schedule.json`: 문제 0개; `scenarios.json` |
| | 24949780, 24949782 | `fae10ba` | `fae10ba`의 일정 확인. 이 커밋은 `b17763d`와 다름 | 24949782: 문제 0개. 24949780(v2106): rank 2개에서 로그 개수 문제 2개(`step 4: 0 snapshots in C++ log, expected 1`, 1단계에서도 같음), 원인은 조사하지 않음; 24950748에는 없음 |
| `dev2212-24952019/` | 24952019 | `d9d1109` | [dev2212_validation.sbatch](dev2212-24952019/dev2212_validation.sbatch): `docker://opencfd/openfoam-dev:2212`에서 받은 이미지(`hpc/README.md`가 적은 이미지)에서 연결 검증. 다른 v2212 작업은 `of2212.sif`를 씀 | PASS, 종료 코드 0 |
| `unit-tests/` | 24951126 | 병합한 `main`(`41ca1bf`) | [unit_merged.sbatch](scripts/unit_merged.sbatch), 새 clone, Python 3.10.22와 3.12.15: `tests.yml`의 모듈 목록, 이어서 `make test` | 테스트 156개, OK, 네 번 |
| | 24950761, 24951079 | `cabcfc6`, `bf7a06e` | [unit_tests.sbatch](scripts/matrix/unit_tests.sbatch), Python 3.10과 3.12 | 156개 OK; PR 트리의 세 모듈, 83개 OK |

matrix 실행은 PR 트리에 없는 케이스 두 개를 씁니다. [version_check_inner.sh](scripts/matrix/version_check_inner.sh)가 실행마다
복사합니다. 작업 24757460의 t = 0.1 s 발달한 유동(`pod-async-v2/run-24757460/.../async-no-llm`)과 작업 24929629의 압출 케이스
(`pod-3d-20261028/run-24929629/case3d`, 164,320셀)입니다. rank 2개에서 스크립트는 케이스의 `pod_svd.py`에서 rank 확인을 뺍니다.
실행마다 OpenFOAM 8이 읽는 `momentumTransport` 파일도 `turbulenceProperties`의 설정으로 더합니다.

[compare_versions.py](scripts/matrix/compare_versions.py)는 병렬 실행이 rank 순서로 모으므로 각 프레임의 셀을 위치로 정렬합니다.
|ΔU|는 셀마다 차이의 크기이고, |Δp|는 각 프레임의 평균 p를 뺀 뒤의 값이며, 프레임의 최댓값과 범위는 짝의 첫 프레임에서 가져옵니다.
`frame-hashes.json`은 각 프레임 파일 네 개의 SHA-256을 적으며, 파일은 클러스터에 남아 있습니다.

`version-compare.json`의 `telemetry_lines_differ_only_in_run_id`는 v2212와 이전 프레임의 비교에서 `false`입니다. 그 실행들이 더
길었기 때문입니다. 처음 110줄에서 텔레메트리는 `end_time_s`와 `run_id`만 다릅니다.

[compare_pod_account.py](scripts/matrix/compare_pod_account.py)는 저장 시각마다 `U`, `p`, `phi`를 해시로 비교합니다. 다르면 파일의
숫자 전체에서 가장 큰 차이를 잡으므로, U에서는 성분 하나의 차이입니다. POD 모드는 셀 값을 비교하고, 모듈이 저장한 스냅샷 행렬은
열마다 비교합니다. 모듈은 각 폴더에 있습니다. `module-recording.py`는 원본에 저장을 더한 것이고, `module-overwrite.py`는 Python에서
원본의 첫 열 덮어쓰기도 재현합니다. `fork-plainp`는 이 포크의 솔버에서 `pEqn.H`의 `#ifdef`를 원본의 단순한 `pEqn.solve()`로 바꾼
것입니다. 제공된 `Run_Case`에서 [pod_account_inner.sh](scripts/matrix/pod_account_inner.sh)와
[upstream_regression_inner.sh](scripts/matrix/upstream_regression_inner.sh)는 `endTime`을 1.5e-4로, `startFrom`을 `startTime`으로,
`writePrecision`을 12로 정하고 `0/uniform/time`을 지웁니다. Docker 작업은 케이스를 바꾸지 않고 돌립니다.

작업 24950817과 24950818은 [submit_suite.sh](scripts/gpu/submit_suite.sh)처럼 `--constraint='l40s|a6000'`으로 제출되었고,
`l40s|a6000|a30`으로 mba30-005에서 시작했습니다([gpu-constraints.txt](gpu-constraints.txt)). [sacct.txt](sacct.txt)의 다른 작업은
제출한 그대로 시작했습니다.

## 빠진 기록

다음은 여기 없고 클러스터의 `pod-versions-20261030/` 아래에 있습니다. 이미지(`.sif`), 솔버 빌드, 시간 디렉터리와 프레임, 요청 본문,
모델 파일, 시험 모음마다의 `run-archive.tar.gz`입니다. 솔버 로그와 텔레메트리는 gzip 사본입니다. 기록 안의 경로는 기록된 그대로입니다.

[hf-no-token.txt](hf-no-token.txt)는 12B 가중치와 프로젝터를 토큰 없이 요청한 두 건을 기록하며, 둘 다 200으로 응답했습니다.
`setup_12b.sh` 자체는 대역 `curl`로만 돌렸고(작업 24950752, 여기 없음), 이 형태로 파일을 받은 적은 없습니다.

[sacct.txt](sacct.txt)에는 작업마다 상태, 노드, 파티션, 시간이 있습니다. 잘못된 설정 작업([그 sacct.txt](../2026-10-30-wrong-setup/job/sacct.txt))과
시작 상태를 만든 실행 24757460([10월 22일](../2026-10-22-live-v2/README.md)), 24929629([10월 28일](../2026-10-28-3d/README.md))는
빠져 있습니다. [manifest.json](manifest.json)에 여기 있는 모든 파일의 크기와 해시가 있습니다.
