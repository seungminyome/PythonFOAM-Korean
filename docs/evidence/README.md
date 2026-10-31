# 근거 자료

시험 날짜별로 한 폴더씩입니다(`2026-10-30-versions`와 `2026-10-30-wrong-setup`에는 10월 30일의 실행이, `2026-10-28-inflight`, `2026-10-28-callback`, `2026-10-28-3d`,
`2026-10-28-instability`에는 10월 28일의 시험이, `2026-10-27-solver`와 `2026-10-27-picture-tests`에는 10월 27일의 솔버 실행과
그림 시험이, `2026-10-19-12b`에는 그날 GPU 노드에서 한 12B 재생이,
`2026-10-22-picture-test`에는 그림 읽기 시험이, `2026-10-22-window-test`에는 그 뒤의 그림 시험이,
`2026-10-22-live-v2`에는 v2 그림으로 한 솔버 실행이 있습니다). 요청, 응답, 배열, 로그는 기록 당시의 바이트를 그대로 두었고(2026-10-20의 솔버 로그와 걸음별 기록은 gzip 사본), 폴더마다 해시 목록이 있습니다.

| 폴더 | 실행 | 코드 | 보고서 |
|---|---|---|---|
| [2026-10-30-versions/](2026-10-30-versions/README.md) | Slurm 작업 24950780\~24950783: OpenFOAM v2012, v2106, v2212, 8에서 빌드, 연결 검증, 모델 없는 관찰 기능; 24950794\~24950797: 대역 서버로 돌린 시험 모음; 24950818, 24950817, 24950804: 모델로 돌린 실행; 24951136\~24951141: 원본 PODFoam과 비교; POD 일정, 원본의 Docker 이미지, 단위 테스트 | `b17763d`(코드는 `bf7a06e`, `main`과 같음, 영문 저장소), 작업마다 기록함 | [results-20261030.md](../results-20261030.md) |
| [2026-10-30-wrong-setup/](2026-10-30-wrong-setup/README.md) | Slurm 작업 24947089: 모델이 실행의 설정이 잘못된 것을 볼 수 있는가? 정상 pimpleFoam 실행 다섯 개와 설정이 잘못된 실행 다섯 개에서 만든 프레임 하나짜리 요청 80개, 모델 네 개; 작업 24946879: 실행; 24946942: 세트 만들기; 정답, 누출 점검, AI 에이전트 하나가 판정한 이유, 프레임이 담은 사실, 다시 세기 | `97db7eb`(수치의 근거: `bc90034`, 영문 저장소) | [results-20261030.md](../results-20261030.md) |
| [2026-10-29-merged-check/](2026-10-29-merged-check/README.md) | Slurm 작업 24936949: 병합한 코드를 빌드하고 검증함, 2차원과 3차원 v2 프레임이 앞선 실행과 같음 | `eff951b`(영문 저장소) | [results-20261028.md](../results-20261028.md) |
| [2026-10-28-inflight/](2026-10-28-inflight/README.md) | Slurm 작업 24929296: 동시에 둘까지 진행하고 서버 슬롯이 두 개인 50걸음마다의 describe 요청, 6,000걸음, 그리고 그 쌍둥이; 하나씩 보낸 10월 27일 실행과 비교 | `2ed6da2`(요약은 `c85c79c`로 다시 만듦, 영문 저장소) | [results-20261028.md](../results-20261028.md) |
| [2026-10-28-callback/](2026-10-28-callback/README.md) | Slurm 작업 24929555(CPU): 계단 경우에서 main의 콜백과 새 콜백, 모델 요청 없이 1,250걸음(describe, sequence, `tn` sequence 형태, MPI rank 2개), 저장 파일 전부와 `telemetry.jsonl` 비교; 기록된 상태 24,000개의 텔레메트리를 tracemalloc 아래에서 재생; 작업 24929607에서 비교를 다시 돌림 | `16d665e`(브랜치 `callback-telemetry-trends`)를 `2ed6da2`와 비교(영문 저장소) | 그 폴더의 README |
| [2026-10-28-instability/](2026-10-28-instability/README.md) | Slurm 작업 24929533과 24929534: 모델이 불안정해지는 실행을 알아볼 수 있는가? 중단된 pimpleFoam 실행 세 개와 안정한 실행 네 개에서 만든 세 프레임 요청 70개, 모델 네 개; 작업 24929408, 24929449, 24929452: 흐름 재계산; 24929495: 묶음 만들기; 24929764: 검토 뒤 점검; 정답과 다시 세기 | `8d6a10a`(보고서 `c9a1ba1`, 검토 뒤 수정 `660f8c4`, 영문 저장소) | 그 폴더의 README |
| [2026-10-28-3d/](2026-10-28-3d/README.md) | Slurm 작업 24929629(그리고 24929500): 평면 단면으로 그린 3차원 경우의 v2 관찰 그림; z 방향으로 칸 8개만큼 늘인 계단 경우를 직렬과 rank 2개로, 관찰 기능 없이, `LLM_SLICE_Z`를 주어서와 거부되게, 2차원 경우와 연결 검증; 모델 없음 | `c7a25d3`(24929500은 `07759b0`, 영문 저장소) | 그 폴더의 README |
| [2026-10-27-solver/](2026-10-27-solver/README.md) | Slurm 작업 24903264: 24,000걸음 동안 250걸음마다 describe 요청과 그 쌍둥이; 작업 24903298과 24903263/24903755: 10월 22일 시험과 sweep의 반복 두 번; 24903786: MPI, rank 2개; 24903065: POD 모드 파일과 BLAS 스레드; 불안정 흐름 시도; 비교와 따라가기 스크립트 | `6afbdeb`에 변경, `df72c24`(작업마다 기록함, 영문 저장소) | [results-20261027.md](../results-20261027.md) |
| [2026-10-27-picture-tests/](2026-10-27-picture-tests/README.md) | Slurm 작업 24903974와 24903975(변화 읽기 시험, 모델 네 개), 24903976과 24903977(권장 이미지 토큰의 4비트 Qwen), 24903978(원기둥 흐름); 원기둥 흐름 계산; 정답과 다시 세기 | `ab6b943`(영문 저장소) | [results-20261027.md](../results-20261027.md) |
| [2026-10-22-live-v2/](2026-10-22-live-v2/README.md) | Slurm 작업 24757460: `pod-llm-async.UM1RyJ`, NVIDIA RTX A6000의 Gemma 4 12B와 v2 그림으로 발달한 흐름에서 시작한 비동기 다섯 조건; 무작위 창 describe 요청 열한 개; 시험 실행(작업 24757458); 검산 스크립트 | `354caf9`(영문 저장소)에 커밋하지 않은 변경(기록함) | [results-20261022-live.md](../results-20261022-live.md) |
| [2026-10-22-window-test/](2026-10-22-window-test/README.md) | Slurm 작업 24757327(Qwen 모델 네 개, 요청 308개), 24757344와 24757382\~24757384(무작위 창, 모델 열한 개, 시드 세 개, 이미지 토큰 한도 1024), 24757459(발달한 흐름, 무작위 창); 발달한 흐름 실행(작업 24757429); 정답과 다시 세기 | 그림 시험 묶음(`58e00d9` + `window_test.py`); 작업 24757459는 작업 24757460과 같음 | [results-20261022-live.md](../results-20261022-live.md) |
| [2026-10-22-picture-test/](2026-10-22-picture-test/README.md) | Slurm 작업 24756981: NVIDIA RTX A6000(MedicineBow)에서 미리 만든 같은 요청 308개를 Gemma 4 모델 일곱 개(E2B부터 31B까지)에 하나씩 보냄. 정답과 독립 재채점 포함 | `58e00d9`(영문 저장소), `7435513`(이 저장소) | [results-20261022.md](../results-20261022.md) |
| [2026-10-20/](2026-10-20/README.md) | `pod-llm-async.pp7agC`: 3000걸음의 비동기 다섯 조건; `pod-llm-async.8YC6bG`: 창 프레임; describe·sequence 재생 | `9449085`(영문 저장소), `74553ea`(이 저장소) | [results-20261020.md](../results-20261020.md) |
| [2026-10-19-12b/](2026-10-19-12b/README.md) | Slurm 작업 24696203: NVIDIA A30(MedicineBow)의 Gemma 4 12B QAT로 한 10월 17일 쌍별 재생, 채점된 위치는 없음(그림 답은 "x=0.00 m 근처"라고만 함) | `934da23`(영문 저장소), `f4a99f3`(이 저장소). 요청·채점 코드는 `23089bb`와 같음 | [results.md](../results.md#gpu에서-gemma-4-12b로-같은-재생-2026-10-19) |
| [2026-10-19/](2026-10-19/README.md) | `pod-llm-demo.o5sNLJ`: 10월 17일 실행과 재생의 반복, 해시와 재생 좌표 동일 | `23089bb` (코드), `4187659` (문서, 영문 저장소) | [results.md](../results.md#2026-10-19-반복) |
| [2026-10-17/](2026-10-17/README.md) | `pod-llm-demo.LRfJBN`: 다섯 솔버 조건과 그림 유무 쌍별 비교 | `23089bb` | [results.md](../results.md) |
| [2026-10-13/](2026-10-13/README.md) | `pod-llm-demo.SwwR2e`: 이미지 경로를 넣은 첫 다섯 조건 실행 | `9ae54d0` | [results-20261013.md](../results-20261013.md) |

10월 27일의 압축 파일(그림 작업 다섯 개, 새 시험 묶음 두 개, 원기둥 계산, 시각 폴더를 뺀 주기 실행, MPI와
POD 파일 실행, 불안정 흐름 시도)은 영문 저장소의
[tests-2026-10-27](https://github.com/seungminyome/PythonFOAM/releases/tag/tests-2026-10-27)
릴리스에 있습니다. 그림 시험의 압축 파일(모든 요청과 정답이 든 입력 묶음, 작업마다 모든 원본 답이 든 결과)은 영문 저장소의
[picture-test-2026-10-22](https://github.com/seungminyome/PythonFOAM/releases/tag/picture-test-2026-10-22)
릴리스에, v2 솔버 실행의 전체 출력, 시험 실행, 발달한 흐름은
[pod-insitu-v2-2026-10-22](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-v2-2026-10-22)
릴리스에 있습니다.

모든 시각 폴더를 포함한 전체 솔버 결과는 저장소가 아니라 릴리스에 있습니다(2026-10-20은 `pod-llm-async.pp7agC`의 다섯 조건. 창 프레임 실행 `pod-llm-async.8YC6bG`은 릴리스에 없고, 이 저장소에는 시각 폴더 없이 프레임과 실행 기록만 있음): [2026-10-20](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-async-2026-10-20)(영문 저장소), [2026-10-17](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18), [2026-10-13](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-demo-2026-10-13).
