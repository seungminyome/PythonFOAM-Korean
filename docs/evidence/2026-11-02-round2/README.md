# 11월 2일 근거: 2차 확인과 최종 PR 브랜치

2026-11-01과 2026-11-02에 와이오밍 대학교 MedicineBow에서 돌린 Slurm 작업입니다. 아래 폴더에 검사마다 기록이
있습니다. 검사 대상은 압력 줄, 형제 솔버 세 개, v2012와 v2212의 오류 시나리오와 POD 일정, OpenFOAM 8이 다른 원인입니다.

불안정했던 단위 테스트, MPI rank 2개의 모델 요청, v2012와 OpenFOAM 8의 12B 시험 묶음, v2212의 기본값
6,000단계, 실제로 내려받은 `setup_12b.sh`도 있습니다. 그 뒤로 3차원 케이스의 단면 이미지, 시점을 적지 않은 불안정 시험,
최종 PR 브랜치의 검사가 이어집니다. 보고서는 [results-20261102.md](../../results-20261102.md)입니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-11-02-round2/README.md)

## 코드

커밋 해시는 영문 저장소 기준입니다. 2차 확인의 실행 대부분은 2026-10-30에 브랜치 `pr/podfoam-observer`였던 PR 트리
`bf7a06e`를 썼습니다. 원본 PODFoam은 `6fde869`의 [argonne-lcf/PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)입니다.
다른 코드를 돌린 폴더는 그 행에 적었습니다.

2차 확인 브랜치 `r2/siblings` `34351f3`, `r2/flaky` `5b2a3de`, `78883f9`, `041a88d`, `r2/gpu-suites` `c82c835`,
`r2/setup12b` `0dfc260`, `2e77ed9`는 로컬에만 있고 GitHub에 없습니다. 그 변경은 최종 브랜치 `473c802`의
`pr/podfoam-fix`와 `cd23736`의 `pr/podfoam-observer`에 있습니다. `r2/instability` `6d38337`은 영문 `main`의 `89733c6`입니다.

기록한 작업 폴더마다 `HEAD`가 있습니다. `git-status.txt`는 `instability/results/gpu-25080221/`의 것만 빼고 모두
비어 있습니다. 그 작업과 세트를 만든 작업 25080121은 `6d38337`의 파일 네 개를 아직 커밋하지 않은 `6677bac`에서
돌았으며, [logs/build-25080121.out](instability/logs/build-25080121.out)에도 그렇게 나옵니다. 네 파일의 SHA-256은
[sha256.txt](instability/results/gpu-25080221/sha256.txt)와 [test-set/manifest.json](instability/test-set/manifest.json)의
`code_sha256`에 있습니다. 이 값은 `6d38337`의 블롭과 같고, `6d38337`은 이 네 파일만 바꿉니다.

## 실행한 것

| 폴더 | 작업 | 코드 | 스크립트 | 보여 주는 것 |
|---|---|---|---|---|
| `pfinal/` | 25080017; 바이너리는 24951137\~24951140의 것 | 포크 `bf7a06e`, 원본 코드 `6fde869`, 이미지의 `pimpleFoam` | [run_demo.sbatch](pfinal/demo/run_demo.sbatch), [inner.sh](pfinal/demo/inner.sh), [summarize.py](pfinal/demo/summarize.py) | 각 풀이가 쓴 압력 솔버 사전을 로그의 솔버 이름으로 읽음(`p` = PCG, `pFinal` = GAMG): [summary.md](pfinal/demo/runs-25080017/summary.md), 솔버 로그 30개의 gzip 사본, OpenFOAM 소스 줄을 인용한 [source-excerpts.md](pfinal/source-excerpts.md), 복사한 소스와 이미지의 md5 비교 [verify-20261102.txt](pfinal/verify-20261102.txt) |
| `siblings/` | 25080208\~25080213(1차), 25088384\~25088390, 25088463(2차; 25088386은 멈춰서 취소했고 25088463이 그 재실행) | 원본 코드 `6fde869`; `34351f3`의 한 줄짜리 소유 배열을 작업 안에서 적용(`ported.diff`) | [siblings.sbatch](siblings/scripts/siblings.sbatch), [inner.sh](siblings/scripts/inner.sh), [sib2.sbatch](siblings/round2/scripts/sib2.sbatch), [inner2.sh](siblings/round2/scripts/inner2.sh), [compare2.py](siblings/round2/scripts/compare2.py), [port_patch.py](siblings/round2/scripts/port_patch.py) | `PODFoam_Debug`, `APMOSFoam`, `AEFoam`을 OpenFOAM 8(제공된 케이스)과 v2106(안정화한 케이스)에서 빌드하고 돌림. 스냅샷 저장을 더한 제공 모듈(`module-recording.py`), Python 복사(`module-copy.py`), C++ 소유 배열: [summary-all.json](siblings/round2/summary-all.json), 실행마다 `result.json`, 포크의 변경 전체를 세 솔버에 대 본 `patch-dry-run.txt`, 작업 25088390의 Keras 시험 |
| `scenarios/` | 25080002(v2012), 25080003(v2212); 25088377\~25088380(추가 세트, v2012, v2212, v2106, 8) | 포크 `bf7a06e`, 원본 코드 `6fde869` | [job.sbatch](scenarios/job.sbatch), [scenarios.py](scenarios/scenarios.py), [schedule.py](scenarios/schedule.py), [job_extra.sbatch](scenarios/job_extra.sbatch), [extra.py](scenarios/extra.py) | v2012와 v2212 각각의 시나리오 46개와 일정 26행을 `2026-10-30-versions/schedule/`의 `ef78700` v2106과 8 기록과 행마다 비교한 [compare4.py](scenarios/compare4.py)와 [compare_sched4_ranks.py](scenarios/compare_sched4_ranks.py)([compare4.json](scenarios/compare4.json), [compare_sched4_ranks.json](scenarios/compare_sched4_ranks.json)); 일정 26행은 네 버전에서 모두 같음; 앞선 [compare_sched4.py](scenarios/compare_sched4.py)는 행 키에 rank 수를 넣지 않아 [compare_sched4.json](scenarios/compare_sched4.json)에는 21행만 있음; `traps-diverging-FOAM_SIGFPE-false`는 OpenFOAM 8에서 돌지 않았고 `traps-env-unset`은 8에서만 돌았으므로, 그 기록까지 합친 시나리오는 이름 47개와 59행; 네 버전의 추가 15행(compare, restart2, collated, traps2, late-overflow)([compare_extra.json](scenarios/compare_extra.json)); 결정적 로그 줄([messages.json](scenarios/messages.json)) |
| `of8-cause/` | 25080020\~25080025, 25080040, 25080041, 25080389 | 이미지의 `pimpleFoam`만; 비교한 프레임은 matrix 실행 24950782와 24950783의 것 | [run.sbatch](of8-cause/run.sbatch), [inner.sh](of8-cause/inner.sh), [run1.sbatch](of8-cause/run1.sbatch), [compare.py](of8-cause/compare.py) | OpenFOAM 8이 v2212와 다른 까닭: `relaxationFactors` 블록의 `fvSolution` 변형 여섯 개([dicts/](of8-cause/dicts)), 100단계와 한 단계, 2차원과 3차원, 모든 차이를 [compare-final.json](of8-cause/compare-final.json)과 [compare-1step.json](of8-cause/compare-1step.json)에; 두 버전의 소스 줄 [source-excerpts-relax.txt](of8-cause/source-excerpts-relax.txt); [NOTES.md](of8-cause/NOTES.md) |
| `flaky/` | 25080033, 25080034(기준); 25080195\~25080198, 25080202, 25080203(고친 테스트); 25088401, 25088402(회귀와 탐침) | `bf7a06e`(기준); `r2/flaky` `78883f9`(부하 실행), `041a88d`(최종) | [load.sbatch](flaky/load/load.sbatch), [run_one.sh](flaky/load/run_one.sh), [regress.sbatch](flaky/regress/regress.sbatch), [probe_refused30.py](flaky/regress/probe_refused30.py), [probe/](flaky/probe)의 탐침 | 8개 동시 부하 속의 `test_connection_refused_is_reported_without_a_stall`, 작업마다 모듈 전체 30회 또는 50회(`.out` 파일, `job.txt`, 실패한 실행의 로그 gzip 사본); cProfile로 잰 원인 [probe-login-20261102.txt](flaky/probe/out/probe-login-20261102.txt); 테스트 모듈 세 개의 회귀와 Python마다 탐침 50회 [regress/](flaky/regress)(`probes-summary.txt`) |
| `gpu-ranks/` | 25080027(대체됨: 래퍼가 자기 pid를 기록하고 프레임 비교가 실패함), 25080066 | 포크 `bf7a06e` | [ranks.sbatch](gpu-ranks/ranks.sbatch), [ranks_inner.sh](gpu-ranks/ranks_inner.sh), [rank_wrap.sh](gpu-ranks/rank_wrap.sh), [check_ranks.py](gpu-ranks/check_ranks.py) | 110단계 중 100단계의 실제 Gemma 4 12B `describe` 요청 하나, 직렬과 MPI rank 2개, v2212와 OpenFOAM 8, NVIDIA A30: [ranks.json](gpu-ranks/run-25080066/ranks.json), [check.out](gpu-ranks/run-25080066/check.out), `llm_result.json`, rank pid 파일, rank 1의 로그, 실행 전후 서버의 `/metrics` |
| `gpu-suites/` | 25080035(v2012), 25080036(8), 25080037(v2212, 기본값 6,000단계); 25080015(기준 실행) | v2012와 8은 `c82c835`: `bf7a06e`에 [async_v2-version-override.patch](gpu-suites/records/async_v2-version-override.patch)의 변경을 더한 것이며, 이 파일은 `async_v2.slurm`이 환경에서 버전을 읽게 하는 단순한 `git diff`입니다; 기본값은 고치지 않은 `bf7a06e` | [submit_suite.sh](gpu-suites/submit_suite.sh), [reference.sbatch](gpu-suites/ref/reference.sbatch), [collect.py](gpu-suites/collect.py), [frame_diff.py](gpu-suites/frame_diff.py) | A30의 Gemma 4 12B로 비동기 케이스 다섯 개: 작업마다 `records/gpu-suite-*/`의 `async-verification.json`, `summary.json`, `site.txt`, `server.cmd`, 셋을 작업 24950817과 나란히 둔 [comparison.json](gpu-suites/records/comparison.json), v2012와 8에서 모델에 요청을 보내지 않은 같은 실행의 프레임을 24950817과 비교한 [frame-diff-vs-24950817.json](gpu-suites/records/frame-diff-vs-24950817.json); `start/`의 시작 디렉터리 격자 점검 |
| `setup12b/` | 25080013(GPU, A30); 내려받기 자체는 Slurm 밖 로그인 노드에서 | `bf7a06e`(제공된 그대로의 `setup_12b.sh`); `fixtest/`는 `r2/setup12b` `0dfc260` | [run_setup.sh](setup12b/run_setup.sh), [test_runtime.sbatch](setup12b/gpu/test_runtime.sbatch) | 토큰 없이 7.9 GB를 실제로 내려받은 `setup_12b.sh`([setup_12b.log](setup12b/setup_12b.log), [sha256.txt](setup12b/runtime/sha256.txt)); GPU 노드에서 스크립트가 둔 그대로의 미리 빌드된 서버(단계 A), soname 링크를 되살린 서버(A2), 소스 빌드(B), 스크립트 재실행(C), 빌드한 서버에 채팅 요청 하나(D)를 `gpu/run-25080013/`에; 고친 스크립트의 실행을 `fixtest/`에 |
| `slice-3d/` | 25080032(CPU: 빌드, 검증, 3차원 300단계 실행 네 개, 시험 세트), 25088316(GPU, L40S: 요청 72개) | 포크 `bf7a06e` | [phase1.sbatch](slice-3d/scripts/phase1.sbatch), [phase1_inner.sh](slice-3d/scripts/phase1_inner.sh), [make_windows.py](slice-3d/scripts/make_windows.py), [phase2.sbatch](slice-3d/scripts/phase2.sbatch), [send_requests.py](slice-3d/scripts/send_requests.py) | 압출한 계단 케이스의 단면 이미지를 `POD_SLICE_Z` 네 개에서 읽는 Gemma 4 12B: 작업 전에 쓴 [design.json](slice-3d/design.json), 시험 세트의 [manifest.json](slice-3d/phase1-25080032/testset/manifest.json), [truth.json](slice-3d/phase1-25080032/testset/truth.json), [baseline.json](slice-3d/phase1-25080032/testset/baseline.json), 응답의 [summary.json](slice-3d/phase2-25088316/results/summary.json)과 [metrics.jsonl](slice-3d/phase2-25088316/results/metrics.jsonl), 요청마다 `result.json`, `response.json`, `metrics.json`; [NOTES.md](slice-3d/NOTES.md) |
| `instability/` | 25080121(세트), 25080221(모델 둘, L40S) | `main` `6677bac` 위의 `r2/instability` `6d38337`(`instability_test2.py`와 `show_time=False` 옵션을 더함) | [build_set.sbatch](instability/jobs/build_set.sbatch), [gpu_models.sbatch](instability/jobs/gpu_models.sbatch), [recount.py](instability/recount.py) | 요청 어디에도 단계와 시점이 없고 두 부류 모두 프레임 간격이 2×10⁻³ s인 불안정 시험: 빌드 전에 쓴 [DESIGN.md](instability/DESIGN.md), 글 동일성 확인이 든 세트의 [manifest.json](instability/test-set/manifest.json)과 정답 [truth.private.json](instability/test-set/truth.private.json), `results/gpu-25080221/12b/`와 `31b/`의 항목별 모델 답, [report.md](instability/results/gpu-25080221/report.md), 10월 28일과 항목별로 비교한 독립 [recount.json](instability/results/gpu-25080221/recount.json) |
| `final-branches/` | 솔버: 25090304\~25090307, 25090315\~25090319, 25090326\~25090330, 25090332\~25090335, 25090337\~25090341, 25090471, 25090475\~25090482. 관찰 예제: 25090610\~25090612, 25090644, 25090645, 25090647, 25090963; 25090613, 25090614, 25090616은 시작 단계에서 멈췄고, 25090615는 시작 전에 취소했으며, 25090646은 GPU 오류를 냈음. 영문 `main`: 25092222. 11월 트리의 부하 실행: 25089961\~25089963. PR 글의 Docker 명령: 25090624, 25092824, 25093622, 25098200 | 최종 `473c802`, `cd23736`과 코드가 같은 `8954b25`, `24e9df6`에서 검사; `main`의 CI 목록은 `main` `71ab2c3`과 코드가 같은 `a1aea2e`에서; 부하 실행은 `276ea8e`와 코드가 같은 `09d7d50`에서 | [fix/jobs/](final-branches/fix/jobs), [observer/jobs/](final-branches/observer/jobs), [main/jobs/ci.sbatch](final-branches/main/jobs/ci.sbatch) | 최종 PR 브랜치의 검사: OpenFOAM v2012, v2106, v2212, 8의 빌드와 검증, Docker 이미지, 원본 PODFoam과의 비교, 시나리오, 형제 솔버, 훅, 3D 단면은 [fix/NOTES.md](final-branches/fix/NOTES.md); 부하 속 단위 테스트, v2106의 E2B 빠른 시작, v2212의 12B 시험 묶음과 rank 2개 요청은 [observer/NOTES.md](final-branches/observer/NOTES.md); 검사 뒤에 README 네 개, `HOOKS.md`, 커밋 메시지, 날짜만 바뀐 것은 [plain/verify_r5.out](final-branches/plain/verify_r5.out), [pr-docs/verify_r6.out](final-branches/pr-docs/verify_r6.out), [pr-docs-r7/verify_r7.out](final-branches/pr-docs-r7/verify_r7.out), [pr-docs-r8/verify_r8.out](final-branches/pr-docs-r8/verify_r8.out), [pr-docs-r9/verify_r9.out](final-branches/pr-docs-r9/verify_r9.out), [pr-docs-r10/verify_r10.out](final-branches/pr-docs-r10/verify_r10.out), [pr-docs-r11/verify_r11.out](final-branches/pr-docs-r11/verify_r11.out), [pr-docs-r12/verify_r12.out](final-branches/pr-docs-r12/verify_r12.out), [pr-docs-r13/verify_r13.out](final-branches/pr-docs-r13/verify_r13.out), [pr-docs-r14/verify_r14.out](final-branches/pr-docs-r14/verify_r14.out); PR 글의 Docker 명령을 8954b25/24e9df6과 d4ebf5c/ca68b32에서 돌린 기록은 [docker-e2e-25090624.out](final-branches/docker-e2e/logs/docker-e2e-25090624.out)과 [docker-e2e-25092824.out](final-branches/docker-e2e/logs/docker-e2e-25092824.out), 최종 브랜치와 코드가 같은 6df2fa2/4414179에서 돌린 기록은 [docker-e2e/r6/](final-branches/docker-e2e/r6/logs/docker-e2e-25093622.out), GitHub에서 복제한 최종 브랜치에서 돌린 기록은 [docker-e2e/github/](final-branches/docker-e2e/github/logs/docker-e2e-25098200.out); 11월 트리에서 부하를 걸고 돌린 `test_async` 모듈 전체, 50회 중 50, 50회 중 50, 30회 중 30은 [load-before-review/](final-branches/load-before-review/load.sbatch); 영문 CI 목록은 [main/logs/ci-25092222.out](final-branches/main/logs/ci-25092222.out); 내려받은 파일로 돌린 최종 `setup_12b.sh`는 [setup12b-check/](final-branches/setup12b-check/setup.out); [sacct.txt](final-branches/sacct.txt) |

pfinal 시연은 검증의 안정화한 케이스를 `p` = PCG/DIC(`relTol` 0.1), `pFinal` = GAMG, `U` = `smoothSolver`, `UFinal` = PBiCGStab로
돌립니다. 그래서 각 `Solving for` 줄의 솔버 이름이 사전을 말해 줍니다([fvSolution](pfinal/demo/runs-25080017/v2106/case-fork-n1/system/fvSolution)).
`fork-plainp`는 단순한 `pEqn.solve()`로 다시 빌드한 포크입니다. OpenFOAM 8에서는 포크의 `#else` 분기가 이미 그 호출이어서 8에는
`fork-plainp` 빌드가 없습니다. `-n1`과 `-n2`는 `nOuterCorrectors` 1과 2입니다.

v2106의 형제 솔버 실행은 `validation/prepare_case.py`의 안정화한 설정을 씁니다. 제공된 `Run_Case`는 세 솔버 모두 89 또는 90단계에서
발산하기 때문입니다(작업 25080211\~25080213; 작업 24951141의 PODFoam과 같음). `AEFoam`은 끝까지 가지 못합니다. TensorFlow 2.20과
Keras 3.15(`pydeps/tf`에 설치, 클러스터에 남아 있음)에서 제공 모듈의 `Input(shape=(int))`가 예외를 내고, 솔버는 `NULL` 반환을 무시한
뒤 다음 단계에서 세그폴트로 멈춥니다. 그래서 그 수치는 학습 호출 전에 쓴 스냅샷 행렬 하나에 기댑니다.

of8-cause의 변형은 A가 matrix 실행 그대로, B가 `relaxationFactors` 블록을 뺀 것, C가 A에 `pFinal 0.9`와 `UFinal 0.9`를 더한 것, D가
완화 없이 솔버 허용 오차를 조인 것, E가 방정식 계수만, F가 필드 계수만 둔 것입니다. [compare.py](of8-cause/compare.py)는 프레임의
`mesh_cells`로 3차원 단면을 고르고 [compare_versions.py](../2026-10-30-versions/scripts/matrix/compare_versions.py)와 같이 비교합니다.

rank 2개 케이스는 10월 30일의 matrix 실행처럼 검증 연결 모듈 `pod_svd.py`의 직렬 전용 확인을 빼고 돌립니다([ranks_inner.sh](gpu-ranks/ranks_inner.sh)).

gpu-suites의 v2012와 8 시작 디렉터리는 작업 24757460의 `0.1` 필드(24950817의 시작과 같은 파일)를 그 버전의 기준 격자 옆에 둔 것이며,
작업 25080015가 만들었습니다([reference.sbatch](gpu-suites/ref/reference.sbatch)). `start/mesh-check-*.txt`는 격자 본문이 같음을,
`boundary-diff-8.txt`는 8의 boundary 파일 표기 차이를 보입니다.

## 뺀 기록

여기에 없고 클러스터의 `pod-versions-20261030/r2/` 아래에 남은 것: 이미지(`.sif`), 솔버 빌드와 복사한 OpenFOAM 소스 파일, 시간
디렉터리, 프레임, 스냅샷 행렬, 단면 세트와 불안정 세트의 그림과 요청 본문, 모델 파일과 `setup_12b.sh`가 내려받은 9 GB 런타임, 시험
모음마다의 `run-archive.tar.gz`, 불안정했던 테스트 부하 작업에서 통과한 실행의 로그(개수는 `.out` 파일에 있음). 솔버 로그와 실패한
테스트 로그는 gzip 사본입니다. 기록 안의 경로는 기록 당시 그대로입니다. `final-branches/`에서 이전 커밋 트레일러의 모델 이름이 나오는 기록 다섯 개는 그 단어 하나만 바꾼 파생 사본이며, 매니페스트에 표시했습니다.

[sacct.txt](sacct.txt)에 작업마다 상태, 노드, 파티션, 시간이 있습니다. 작업 25088386은 취소한 형제 솔버 작업이며 25088463으로 다시
돌렸습니다. 시작 상태를 만든 작업 24757460([10월 22일](../2026-10-22-live-v2/README.md))과 24929629([10월
28일](../2026-10-28-3d/README.md)), pfinal 시연이 바이너리를 가져온 작업 24951137\~24951140([10월
30일](../2026-10-30-versions/README.md))은 그 폴더에 있습니다. [manifest.json](manifest.json)은 여기 모든 파일을 크기와 해시와 함께
적습니다. [make_evidence.py](make_evidence.py)가 파일을 복사하고 manifest를 썼습니다.
