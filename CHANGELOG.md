# 변경 기록

날짜는 실행이나 변경이 있었던 날입니다. 기록된 실행에는 그 실행을 만든 코드 버전을 적었습니다.

## 2026-10-30, 10월 30일 보고서; 최종 코드에서 버전 시험 (영문 저장소의 `cabcfc6`, PR 트리 `bf7a06e`)

- `compat-final`(`cabcfc6`)을 `main`에 병합. PR 트리: 브랜치 `pr/podfoam-observer`, `bf7a06e`. 둘이 함께 가진
  `Solver_Examples/PODFoam` 아래 코드는 blob이 같음
  ([code-identity.txt](docs/evidence/2026-10-30-versions/code-identity.txt)).
- 새 문서 [docs/results-20261030.md](docs/results-20261030.md),
  [docs/evidence/2026-10-30-versions/](docs/evidence/2026-10-30-versions/README.md).
  v2012, v2106, v2212, 8에서: 검증과 모델 없는 관찰 기능, 2차원과 3차원, 직렬과 rank 2개(작업 24950780\~24950783),
  대역 서버로 돌린 시험 모음(24950794\~24950797), 12B 요청 하나(24950818, A30; 24949167, L40S). v2212의 12B 시험
  모음(24950817, A30; 24949283, L40S), v2106에서 PR 트리의 E2B 빠른 시작(24950804), 원본의 Docker 이미지(24950798).
- `bf7a06e`에서 원본 PODFoam과 비교(작업 24951136\~24951141): OpenFOAM 8에서 U, p, phi는 바이트까지 같음. Python에서
  첫 스냅샷 덮어쓰기를 재현하면 POD 모드가 같음(30개 중 30개, 150개 중 150개). openfoam.com에서는 원본의 압력 줄도 쓰면 같음.
- 단위 테스트: 병합한 `main`에서 Python 3.10과 3.12로 156개(작업 24951126). PR 트리는 모듈 여덟 개 중 세 개, 83개(작업 24951079).
- `README.md`: OpenFOAM v2012, v2106, v2212, 8; 빠른 시작의 `PYTHON`; 12B 저장소가 토큰 없이 응답하므로 `HF_TOKEN`은
  선택 사항(근거 자료의 `hf-no-token.txt`). `hpc/README.md`: 같은 내용; 지금의 `async_v2.slurm`을 GPU에서 돌림. 이 코드에서
  `opencfd/openfoam-dev:2212`로 연결 검증(24952019). `llm_demo/README.md`: 버전, POD 일정, 테스트 수. 이전 수: 잘못된 설정 시험
  전인 2026-10-29에 125개(Python 3.11), 불안정 시험과 단면 시험을 병합하기 전인 2026-10-28에 108개, `TMPDIR`를 노드의 로컬
  디스크에 둔 경우와 NFS에 둔 경우.

## 2026-10-30, PR 파일 검토

- `PODFoam`: 모듈의 `SystemExit`가 더는 실행을 그 종료 코드로 끝내지 않음. 실행을 시작한 폴더가 `sys.path`에 남음. 원본의
  시간 측정 줄 네 개가 돌아옴. 모든 rank가 같은 수의 POD 모드를 돌려주고 같은 훅을 정의해야 함. 셀이 없는 rank를 받아들임.
  `LLM_SLICE_Z`는 이제 `POD_SLICE_Z`.
- `validation/`: 기준 복사본은 기록만 함. 케이스 편집마다 해당 문장을 찾아야 함. Python 3.6에서 돎. 스크립트는 기본으로 이미
  source한 OpenFOAM과 `PATH`의 `python3`를 씀.
- `run_demo.sh`와 `pack_run.py`는 `runtime.py`와 같은 기본 런타임 폴더를 씀. `LLM_LONG_CASES`가 있으면 더는 `PASS`를 출력하지
  않음. `setup_12b.sh`는 토큰이 필요 없고 토큰을 명령줄에 두지 않음. `LLM_HTTP_PYTHON`의 기본값은 실행 중인 Python.
- PR을 위해 공유 파일에서 옮김: 안정성 요청은 `stability_request.py`로, sweep 작업은 `hpc/async_v2_sweep.slurm`으로, main의
  콜백과의 비교는 `test_callback_main.py`로, `/results/`와 `/work/`는 각자의 `.gitignore`로. `async_v2.slurm`은 더는 추적하지
  않는 파일을 묶지 않음.

## 2026-10-30, OpenFOAM 버전; 클러스터 기본값 없는 HPC 스크립트 (영문 저장소의 `cc61adb`, `4a8f59c`, `cf61575`)

- PODFoam이 OpenFOAM v2012, v2106, v2212, 8에서 빌드됨(`PythonCompat.H`). `cf61575`에서 네 버전 모두 연결 검증이 통과하고,
  모델 없는 관찰 기능이 2차원 계단 케이스와 3차원 단면 케이스를 직렬과 rank 2개로 돌림(Slurm 작업 24947448\~24947451,
  24947494, 24947501, 24947502, 24947507). openfoam.com 버전은 원래 케이스의 발산을 재현함. OpenFOAM 8에서 그 케이스는 트랩을
  꺼도 켜도 발산하지 않음.
- OpenFOAM 8의 한계 두 가지, `PythonCompat.H`에 적음: 실행 중 `maxIter 0`으로 풀이가 멈춘 필드는 마지막 목록을 계속 보고함(운동량
  예측자를 끈 경우는 확인함). `moveMeshOuterCorrectors`가 있는 움직이는 격자에서는 마지막 외부 보정의 풀이만 보고함.
- `frame_scoring.py`에 정답과 점수를 둠. 그래서 `verify_async.py`와 핵심 테스트에 실험 스크립트가 필요 없음. 이전 모듈은 같은
  이름을 그대로 줌. `test_picture_test.py`는 시험 스크립트를 불러와 그 이름들을 확인함. 단위 테스트: 모듈 여섯 개에 127개.
- `async_v2.slurm`, `periodic_v2.slurm`: `SIF`와 `PYTHON`이 필수이고, 없으면 작업이 바로 멈춤. 호스트 모듈은
  `POD_HOST_MODULES`에서만 가져옴. 없으면 소스에서 빌드한 llama-server가 시작하지 않음(`libcudart.so.12`를 못 찾음). `site.txt`가
  이 설정을 기록하고, `OPENFOAM_BASHRC`를 지정할 수 있음. 이 형태로 두 스크립트는 stub 명령으로만 돌림.
- `picture_test.slurm`, `window_test.slurm`: 올리기에는 `RESULTS_REPO`가 필요하며 기본 저장소는 더 없음. `RESULTS_RELEASE`는 있고
  `RESULTS_REPO`나 `GH_TOKEN`이 없는 작업은 아무것도 올리지 않는다고 출력함.

## 2026-10-30, 잘못된 설정 시험 (영문 저장소의 `97db7eb`)

- 새 파일 `wrong_setup_test.py`, `test_wrong_setup_test.py`(테스트 27개; `97db7eb`에서 모두 152개, 병합 뒤 154개; `make test`와 CI가
  돌림). 시스템 프롬프트가 의도한 설정을 알려 주고 실수의 종류를 말하지 않을 때, 모델이 프레임 하나의 이미지에서 실행의 설정이
  잘못된 것을 볼 수 있는가? `check`는 요청 문장으로 부류를 가를 수 있는 세트를 거부함. 10월 28일 불안정 세트의 결함임.
- 실행: 정상 실행 다섯 개와 항목 하나를 바꾼 실행 다섯 개, 각 8,000단계(작업 24946879), 요청 80개, 모델 네 개(작업 24947089).
  80개 중 맞힌 수: Gemma 4 31B 67, 12B 41, 26B-A4B 42, Qwen3.5-35B-A3B 45; 상수 기준선 40; 최대 |U| 규칙 56. 기록은
  [docs/evidence/2026-10-30-wrong-setup/](docs/evidence/2026-10-30-wrong-setup/README.md).
- 이 수의 근거, 답을 읽은 뒤 계산함: 점성 실행과 변경이 이미지에 없는 움직이는 벽 실행을 빼면 64개 중 31B 55, 규칙 56. 가장 큰
  Courant 수가 1을 넘는지 보면 기준 실행 없이 잘못된 실행 다섯 개 중 세 개를 찾음(80개 중 64개). 정상 실행이 있으면 색 막대의 숫자만으로
  80개 중 75개(정상 실행을 하나씩 빼면 68개). 점성 실행은 모델이 알아채는 듯하고 그런 수치로는 잡히지 않는 유일한 변경이며,
  실행 하나이고 이유 대부분이 실제로 있는 재순환을 없다고 함. 이유는 AI 에이전트 하나가 판정함: 37개 중 14개는 변경이나 그 눈에 보이는
  효과를 말하고, 17개는 부분적으로, 6개는 말하지 않음. `wrong_setup_test.py`, 실행, 질문, 채점은 바뀌지 않음.

## 2026-10-29, 문서

- README는 비슷한 분야(솔버 연동과 in-situ 분석 도구, CFD 머신러닝, 멀티모달 평가)에서 널리 쓰이는 저장소 13개의 README 절
  비율을 따름: 기능, 대표 결과 두 줄, 비동기 v2 경로 흐름도, 요구 사항, 빠른 시작, 설정, 출력 파일, 한계, 문서 안내,
  인용, 감사의 글, 라이선스. 영문 기준 약 1,200단어.
- 웹페이지는 결과 페이지가 됨: 상수 기준선 열이 있는 결과 표, 주요 발견, 한계, 모든 보고서와 근거 자료, 내려받기
  링크. 두 곳 모두 맨 위 이미지는 실행 중인 솔버가 보낸 v2 이미지 두 장.
- 10월 27일과 28일 보고서는 결과 요약으로 시작하고, 용어 정의와 한계를 한 번씩만 적고, Slurm 작업은 '기록' 절에 둠.
  '답 하나로 고정'은 '상수 기준선'으로 바꿈. 숫자는 바뀌지 않음.
- 10월 27일 보고서 정정: v2own 이미지에서 26B-A4B의 최대 속도 추세 오답은 대부분 2 % 미만의 변화에서 나옴(14개 중
  9개). 오답이 주로 뚜렷한 변화에서 나온 모델은 31B와 Qwen3.5뿐.
- 10월 28일 보고서 요약에 불안정 감지 시험 세트의 결함을 적음: 요청마다 적은 프레임 시점만으로도 두 부류가 구분됨.
- 10월 27일 추적 그래프를 (a) 최저 압력, (b) 최대 속도 두 패널로 다시 그림(`tracking.py`, manifest 갱신, 숫자는 같음).
- 한국어 용어 통일: 시간 단계, 셀, 표시 영역, 상수 기준선, 시퀀스, 이미지, 유동 등. 이전 용어의 대응표는 결과 페이지의
  보고서 절에 있음.
- 물결표(\~) 범위가 GitHub에서 취소선으로 보이던 문서 13개를 고침(`\~`). 근거 자료 README 6개는 manifest도 갱신.

## 2026-10-29, 솔버 실행으로 확인한 병합한 코드 (영문 저장소의 `eff951b`)

- 콜백, instability-test, observer-3d 브랜치를 병합한 뒤: 빌드와 연결 검증 PASS. 2차원 v2 프레임과 요청 본문은
  2026-10-27 MPI 시험의 것과, 3차원 단면 프레임과 요청 본문은 단면 시험(작업 24929629)의 것과 같음. 두 경우 모두
  `telemetry.jsonl`이 완전함(Slurm 작업 24936949). 기록
  [docs/evidence/2026-10-29-merged-check/](docs/evidence/2026-10-29-merged-check/README.md).
- CI도 `test_instability_test`를 돌림: 테스트 모듈 여섯 개, 125개로 `make test`와 같음.

## 2026-10-28, 요청 두 개 동시 진행 (영문 저장소의 `2ed6da2`로 실행; `c85c79c`, `56646b9`)

- `start_server.sh`: `LLM_PARALLEL`이 서버 슬롯 수를 정함. `periodic_v2.slurm`이 `LLM_CTX`와 `PERIODIC_WRITE`를
  환경에서 받음(`289f72c`).
- 실행: 기다리는 요청 최대 둘, 서버 슬롯 둘로 50걸음마다 describe 요청, 6,000걸음, 그리고 그 쌍둥이(작업
  24929296). 답을 받은 요청 하나에 `llm_result.json`이 없어서 실행기가 요약에서 멈춤. 한도가 있는 쓰기 프로세스가
  0.2 s 정리 한도에서 멈췄기 때문.
- `run_periodic.py --summary-only`는 끝난 실행의 요약을 다시 만듦. 답을 받았지만 기록이 없는 요청은 `records_missing`에
  적고 점수에서 뺌. `max_requests_in_flight`(`c85c79c`).
- `python_module.py`: 요청 목록이 요청마다 `record_written`을 기록함. 한도를 넘게 느려진 쓰기 프로세스로 하는
  새 테스트(`56646b9`, 2026-10-29).
- 보고서 [docs/results-20261028.md](docs/results-20261028.md), 기록
  [docs/evidence/2026-10-28-inflight/](docs/evidence/2026-10-28-inflight/README.md), 압축 파일은 영문 저장소의
  `tests-2026-10-28` 릴리스.

## 2026-10-28, 콜백: 모든 상태를 쌓아 두지 않는 텔레메트리, 계산한 증감 단어 (영문 저장소의 `16d665e`)

- `python_module.py`: 마지막 걸음에서 모든 상태의 기록으로 `telemetry.jsonl`을 다시 쓰지 않음. 걸음이 오면 그
  줄을 인코딩하고, 마감이 있는 포크한 자식 프로세스가 500줄 또는 60 s마다 대기 중인 줄을
  `telemetry.jsonl.tmp`에 덧붙이며, 마지막 걸음이 나머지를 덧붙이고 파일 이름을 바꿈. 끝난 파일은 전과 바이트가
  같음. 콜백은 첫 상태와 마지막 세 상태(SVD 요약의 창 시작과 잔차 추세)만 남김. 요청 워커는 더는 텔레메트리를
  쓰지 않음. 10월 27일 주기 실행에서 기록된 상태 24,000개에서 Python 힙은 31.7 MiB까지 느는 대신 최대
  0.515 MiB(tracemalloc의 최댓값; 마지막 상태 뒤 0.067 MiB, 그 상태는 덧붙인 직후에 옴)에 머물렀고, 마지막
  걸음은 0.699 s 대신 0.023 s 걸림. 이제 걸음마다 줄을 인코딩하고(PODFoam에서 걸음당 콜백 시간 중앙값이
  0.079\~0.107 ms에서 0.163\~0.217 ms로 오름), 덧붙이는 걸음은 13.7\~22.0 ms 걸림.
- v2 sequence: `llm_result.json`이 `computed_trends`(그린 범위 안 프레임 배열에서 구한 정답의 증감 단어 세 개)와,
  모델의 단어와 견준 `computed_trends_agreement`를 기록함. 새로 보내는 것은 없음. `LLM_SEQUENCE_PROMPT=t`나
  `tn`은 10월 27일 변화 읽기 시험의 `-t`나 `-tn` 형태를 보냄. 기본 요청은 바이트까지 그대로.
- `verify_async.py`는 실행에 `computed_trends`와 `t`/`tn` 본문이 있으면 확인함.
- 테스트: main의 콜백과 견준 텔레메트리(2,345걸음, 묶음 크기 둘), 6,000걸음 동안의 메모리, 끊기거나 실패하거나
  버려진 덧붙이기, 인코딩할 수 없는 상태, 시간 조건; 그림 시험의 함수와 견준 계산한
  증감 단어, `t`와 `tn` 본문, 거부; 전체 107개.
- 실행: Slurm 작업 24929555(CPU, mbcpu-010): 준비한 계단 경우에서 main의 콜백과 이 콜백, LLM_ENABLED=0으로
  1,250걸음, 100걸음에 describe, 100, 150, 200걸음에 sequence, `tn` 형태, rank 2개의 describe 경우. 저장 파일,
  `telemetry.jsonl`(1,250줄), 요청 본문이 모두 main과 브랜치 사이에 같음. 기록은 실행마다 달라지는 값과 새
  `computed_trends`만 다름. `tn` 본문은 시험한 빌더와 같음. rank 2개에서는 로그 줄이 정렬한 목록으로만 맞고,
  POD 점검 파일은 두 실행 모두에서 읽을 수 없음(두 rank가 모두 씀). 그것을 처리해 비교를 다시 돌림(작업
  24929607). 기록 [docs/evidence/2026-10-28-callback/](docs/evidence/2026-10-28-callback/README.md).

## 2026-10-28, 불안정 시험 (영문 저장소의 `8d6a10a`, 보고서 `c9a1ba1`, 검토 뒤 수정 `660f8c4`)

- `readable_request.py`: `STABILITY_V2OWN_SYSTEM_PROMPT`와 `stability_v2_payload()`는 v2 프레임 세 장(그림마다
  제 색 범위)에 수치 불안정의 징후가 보이는지 물음. `llm_client.py`에 `stability` 답 스키마(`reason`, 그다음
  `stable`, `unstable`, `cannot_tell` 중 하나). `LLM_MODE`가 아니므로 솔버는 여전히 거부함.
  `snapshot_runner.py`가 채점하고 `picture_test.py`가 요약함. 기존 요청 본문은 바이트까지 그대로(골든 테스트).
- 새 `instability_test.py`: pimpleFoam 실행으로 묶음을 만들고(중단된 실행은 중단까지 남은 걸음으로 이름 붙인
  `unstable` 묶음, 끝까지 돈 실행은 `stable` 묶음), `picture_test.py`로 돌리며, 균형 점수, `unstable`이라고
  얼마나 일찍 말하는지, 실행별 답, 숫자 기준선 두 개를 보고함. 새 `test_instability_test.py`(`660f8c4`부터
  12개; `test_llm_client`, `test_callback`, `test_ablation_runner`, `test_async`, `test_picture_test`와 함께
  107개, 어떤 순서로든, `unittest discover`로도).
- 실행: t = 0.1 s부터 다시 돌린 `central-dt2e-5`는 467걸음에서 중단(작업 24929408). 풍상 실행 두 개(2,000걸음)와
  `central-dt5e-6`(4,000걸음)은 끝까지 돎(24929452, 24929449). 시험 묶음 만들기(24929495). 그 요청 70개에
  Gemma 4 12B, 26B-A4B, 31B, Qwen3.5-35B-A3B(24929533, 24929534). 기록
  [docs/evidence/2026-10-28-instability/](docs/evidence/2026-10-28-instability/README.md).
- 검토 뒤 수정(`660f8c4`). `instability_test.main()`이 `picture_test`의 묶음 목록을 바꾸고 되돌리지 않아서,
  `unittest discover`처럼 한 프로세스에서 `test_instability_test` 뒤에 `test_picture_test`가 돌면 실패했음(오류
  3개). 이제 `main()`이 오류가 나도 되돌림. 로그에 부동소수점 예외 추적(`Foam::sigFpe`)이 있고 `End`가 없을
  때만 중단으로 셈. `report`는 서로 다른 정답으로 만든 실행 폴더를 거부함. 이 코드로 다시 만든 묶음은 정답과
  요청 본문이 같고, `report`는 같은 보고서를 냄(작업 24929764). 근거 자료 README에 이제 적음: 요청에 적힌
  프레임 시각만으로 두 부류가 갈린다는 것(채점 항목 54개 중 54개), 풍상 실행이 중단된 실행의 Courant 수와
  대부분 겹치지만 전부는 아니라는 것, 중심 차분 실행의 창 밖에서 가장 큰 |U|가 어디인지
  (`flow/domain_max.py`).

## 2026-10-28, 평면 단면으로 그린 3차원 경우의 v2 그림 (영문 저장소의 `07759b0`, `127a1dc`, 검토 뒤 수정 `5706021`)

- PODFoam: 3차원 경우(`empty` 패치 없음)는 이제 관찰 기능에 평면 단면의 다각형을 줌(`PythonSlice.H`).
  OpenFOAM의 `cuttingPlane`을 z = `LLM_SLICE_Z`에(기본은 격자 z 범위의 가운데; 격자점을 지나는 평면은 위쪽
  다음 점 평면까지의 절반만큼 옮김), 법선 (0 0 1), 삼각형으로 나누지 않고, 잘린 칸마다 다각형 하나. 기존
  `mesh_func` 인자로, rank별 오프셋과 마스터로 모으기를 거쳐 넘어가고, 여덟 번째 인자가 평면을 설명함. 2차원
  경우는 전과 같은 인자 일곱 개 호출. `Make/options`: surfMesh와 fileFormats include, `-lsurfMesh`.
- `python_module.py`, `pod_image.plane_slice`, `readable_request.py`: 3차원 경우의 v2 프레임은 단면 칸만
  담고(중심, U, p, 그리고 `fields.npz`에 그 격자 칸과 다각형), 메타데이터에 단면을 기록함. 요청은 2차원과 같이
  만듦. v1은 3차원에서 래스터를 그대로 씀. 2차원 프레임은 전과 바이트까지 같게 씀.
- 테스트: `test_async.py`에 합성 형상으로 하는 단면 테스트 네 개; 전체 99개.
- 실행: 작업 24929629(그리고 `07759b0`로 돈 24929500, 파일 같음), z 방향으로 칸 8개만큼 늘이고 앞뒤를 벽으로
  막은 계단 경우, 모델 없음. 직렬과 rank 2개의 단면 프레임이 같은 칸 20,540개를 담고, U는 2.5×10⁻³ m/s, p는
  0.036 m²/s² 안. 관찰 기능이 있는 실행의 저장 필드가 없는 실행과 같음(파일 63개). 2차원 프레임은 2026-10-27의
  것과 같음. 연결 검증 통과. 기록 [docs/evidence/2026-10-28-3d/](docs/evidence/2026-10-28-3d/README.md).
- `llm_demo/README.md`: "솔버 안에서 호출되는 순서"에 3차원 경우; `LLM_SLICE_Z`. 근거 자료 목록: 새 폴더.

## 2026-10-27, 변화 읽기, 4비트 Qwen, 원기둥 흐름, 250걸음마다 요청, MPI (영문 저장소의 `6afbdeb`, `df72c24`, `ab6b943`)

- `readable_request.py`: 정답의 기준을 적거나(`thresholds=True`), 시각마다 극값을 메모에 더하거나
  (`numbers=`), 그림 없이 메모만 보내는(`images=False`) sequence 프롬프트. 기본값이면 본문은 바이트까지 그대로.
  새 `sequence_test.py`는 저장 상태로 변화 읽기 묶음을 다섯 가지로 만듦. `window_test.py`와
  `sequence_test.py`가 `--dt`와 `--y-span`을 받음.
- `python_module.py`: `LLM_ANALYSIS_EVERY=N`이면 N걸음마다 describe 요청을 보내고(v2만), 요청마다
  `llm_requests/step-NNNNNN/`에 기록하고 목록을 씀. 워커 파이프로 오간 바이트를 기록. `LLM_KILL_JOIN_S`
  기본값 0.1 s. 새 `run_periodic.py`와 `hpc/periodic_v2.slurm`은 요청이 있는 긴 실행과 그 쌍둥이를 돌려 비교함.
- PODFoam: 병렬 실행에서 격자와 필드를 마스터 rank로 모으고(`PythonGather.H`), 마스터만 `mesh_func`와
  `analysis_func`를 부름. Python 경로에 경우의 최상위 폴더가 들어감. `pod_image.py`는 2차원 패치가 두 면을
  모두 담고 있어도 칸마다 다각형 하나만 남김.
- GPU 스크립트: `models.tsv`에 4비트 Qwen 줄; `start_server.sh`가 `LLM_IMAGE_MIN_TOKENS`를 넘김;
  `window_test.slurm`이 `PICTURE_TEST_SCRIPT`를 돌리고 `POD_HOST_MODULES`를 불러옴; `POD_SUITE_RUN`을 주면
  `async_v2.slurm`은 sweep만 돌림. `pack_run.py`는 빌드 뒤에 바뀐 원본이 있으면 묶기를 거부하지 않고 기록함.
- 테스트: 주기 요청, 그 기록과 거부; 전체 95개.
- 실행: 변화 읽기 시험(작업 24903974, 24903975), 4비트 Qwen(24903976, 24903977), 원기둥 흐름(24903978과 흐름
  계산), 24,000걸음 동안 250걸음마다 요청(24903264), 10월 22일 솔버 실행의 반복 두 번(24903298, 24903263과
  24903755), MPI(24903786), POD 파일(24903065), 불안정 흐름 시도. 보고서
  [docs/results-20261027.md](docs/results-20261027.md), 기록
  [docs/evidence/2026-10-27-picture-tests/](docs/evidence/2026-10-27-picture-tests/README.md)와
  [docs/evidence/2026-10-27-solver/](docs/evidence/2026-10-27-solver/README.md), 압축 파일은 영문 저장소의
  `tests-2026-10-27` 릴리스.
- README, 근거 자료 목록, 페이지 목록, `llm_demo/README.md`, `hpc/README.md`에 결과를 넣고, 남은 문제와
  다음 단계를 고침.

## 2026-10-22, 돌고 있는 솔버가 그린 v2 그림, 무작위 창, Qwen 모델 (`354caf9`에 커밋하지 않은 변경으로 실행; 코드 `dee7731`, 이 저장소의 `f26bac5`로 공개)

- `llm_demo/`에 새로: `readable_request.py`(v2 요청 빌더. `picture_test.py`에서 옮겨 와 그림 시험과 콜백이
  함께 씀), `run_live_sweep.py`(돌고 있는 솔버의 여러 걸음에서, 걸음마다 무작위 창으로 describe 요청),
  `window_test.py`(가장 빠른 칸 둘레에 창을 무작위로 놓은 그림 묶음). `llm_demo/hpc/`에
  `async_v2.slurm`(v2 그림 비동기 시험과 sweep. OpenFOAM은 Apptainer 이미지에서, llama-server는 호스트
  GPU에서)과 `window_test.slurm`; `models.tsv`에 Qwen 네 줄; `start_server.sh`가 `LLM_IMAGE_TOKENS`를 읽음.
- `python_module.py`: `LLM_IMAGE_STYLE=v2`이면 `describe`와 `sequence` 요청에 필드마다 그림 한 장을 그리고,
  프레임마다(배열, 그림, 마지막에 메타데이터) 폴더 하나에 쓰며, 이전 실행이 남긴 프레임은 덮어쓰지도
  보내지도 않음. v2 요청은 `max_tokens` 320, 그림 시험의 시드, 프롬프트 캐시 없음으로 보내고, v2 describe
  요청은 SVD 창을 쌓지 않음. `LLM_KILL_JOIN_S`로 끊은 워커를 거두는 시간을 정함. 기본값(`v1`)은 그대로.
- `run_async_cases.py`, `verify_async.py`: `LLM_LONG_START`로 모든 경우를 발달한 상태에서 시작(격자와 시작
  파일은 해시로 확인). v2 실행에서는 요청 본문이 디스크의 프레임에 빌더를 적용한 결과와 바이트까지
  같은지, 프레임 배열이 저장 필드와 같은지 확인하고 답을 채점. `run_demo.sh`와 `validation/run_v2106.sh`는
  OpenFOAM 버전을 `POD_OPENFOAM_VERSION`에서, Python 라이브러리 이름을 인터프리터에서 얻음.
  `pack_run.py`는 작업 스크립트가 호스트에서 기록한 git 상태를 담음.
- 테스트: 발표된 그림 시험 요청 두 개를 그 그림으로부터 바이트까지 다시 만들고 다섯 개는 해시로 고정하는
  골든 테스트; v2 콜백 테스트(describe, sequence, 거부, 같은 폴더에서 다시 돌리기); 전체 92개.
- 실행: 발달한 흐름에서 v2 그림과 Gemma 4 12B로 비동기 다섯 조건과 sweep 요청 열한 개(작업 24757460);
  모델 열한 개, 창 시드 세 개, 더 큰 이미지 토큰 한도의 무작위 창 시험(작업 24757344, 24757382\~24757384);
  발달한 흐름의 무작위 창(작업 24757459); 요청 308개에 Qwen 모델 네 개(작업 24757327); 흐름 계산
  24757337과 24757429. 보고서 [docs/results-20261022-live.md](docs/results-20261022-live.md), 기록
  [docs/evidence/2026-10-22-live-v2/](docs/evidence/2026-10-22-live-v2/README.md)와
  [docs/evidence/2026-10-22-window-test/](docs/evidence/2026-10-22-window-test/README.md), 압축 파일은 영문
  저장소의 새 `pod-insitu-v2-2026-10-22` 릴리스와 `picture-test-2026-10-22` 릴리스.
- README, 근거 자료 목록, 페이지 목록, `llm_demo/README.md`, `hpc/README.md`에 결과를 넣고, 남은 문제와
  다음 단계를 고침. `.gitignore`가 모든 `pod-*.out` 작업 로그를 제외함.

## 2026-10-22, 그림 읽기 시험 (2026-10-21 준비, 코드 `58e00d9`, 이 저장소의 `7435513`, Slurm 작업 24756981로 실행)

- `llm_demo/`에 새로: `readable_image.py`(그림 한 장에 필드 하나, 축은 그린 범위의 퍼센트와 10 %마다
  격자선, 색 막대에 최솟값부터 최댓값까지 값 다섯 개), `foam_fields.py`(ASCII OpenFOAM 필드와 empty
  패치 다각형 읽기), `picture_test.py`(정해 둔 그림 요청 묶음을 만들고, 확인하고, 보내고, 모델에게
  보이지 않은 정답으로 채점해 보고서를 냄),
  `test_picture_test.py`(테스트 13개, 전체 83개). `llm_demo/hpc/`에 `models.tsv`(Gemma 4 모델 일곱 개,
  리비전과 해시 고정), `fetch_models.sh`, `picture_test.slurm`. `start_server.sh`와 `stop_server.sh`는
  모델·문맥·batch·상태 폴더를 바꿀 수 있고, 바꾸지 않으면 예전과 같음.
- 실행: NVIDIA RTX A6000 한 장에서 Gemma 4 모델 일곱 개(E2B 세 가지, E4B, 12B, 26B-A4B, 31B)에 요청
  308개씩. 보고서 [docs/results-20261022.md](docs/results-20261022.md), 정답과 독립 재채점이 든 기록
  [docs/evidence/2026-10-22-picture-test/](docs/evidence/2026-10-22-picture-test/README.md), 두 압축
  파일은 영문 저장소의 `picture-test-2026-10-22` 릴리스.
- README, 근거 목록, `hpc/README.md`, `llm_demo/README.md`, 첫 화면(`index.html`), 작업 기록에 결과를
  넣고 남은 문제와 다음 단계를 고침. 그림으로 보는 10월 17일 결과와 그림 해설 두 쪽의 안내문에 한
  줄씩 더함. `hpc/README.md`와 `models.tsv`의 설명: e2b-qat는 프로젝터 파일도 다르다는 것(e2b-bf16처럼
  BF16), 저장 상태에서 같은 것은 흐름이 아니라 추세 단어라는 것. `Makefile`: 테스트는 약 30초.
- 입력 묶음을 클러스터로 옮기는 데 쓴 영문 저장소의 임시 사전 릴리스 `picture-test-input-20261021`은
  지움. 그 묶음은 새 릴리스에 있음.

## 2026-10-20, 12B 재생 공개 (2026-10-19 실행, 코드 `934da23`, 이 저장소의 `f4a99f3`)

- NVIDIA A30에서 Gemma 4 12B QAT로 한 10월 19일 쌍별 재생의 기록을
  [docs/evidence/2026-10-19-12b/](docs/evidence/2026-10-19-12b/README.md)에 둠: 요청 6개와 답, 작업
  스크립트와 출력, Slurm 사용 기록, 서버·빌드 로그, 해시 목록, 답을 사람이 검토한 기록. 여섯 답 모두
  위치를 모른다고 함. 요청당 2.0\~3.3 s.
- 10월 17일 보고서에 새 절, README에 12B 표. 12B를 시험하지 않았다는 문장을 바로잡음(README, 10월 20일
  보고서, `hpc/README.md`, 작업 기록). 첫 화면(`index.html`)에는 12B 절을 새로 넣음. 그림으로 보는 10월 17일 결과(`results-20261017.html`)와
  그림 해설 두 쪽(`guide.ko.html`, `overview.ko.html`)의 안내문에 12B 재생을 한 줄씩 더함.
- `hpc/README.md`: MedicineBow의 설정 줄과 llama.cpp 소스 빌드를 적은 "시험한 곳"(미리 빌드된 b11429
  라이브러리는 GLIBC_2.38이 필요). 12B 서버는 이미지 토큰 상한을 128로 낮춤.
- `replay_12b.slurm`, `demo_12b.slurm`: `HF_TOKEN`은 가중치를 내려받을 때만 필요. 계정과 파티션은
  `sbatch` 명령줄에서 줌. `setup_12b.sh`는 쓰고 있는 `llama-server`의 해시도 기록.
- `.gitignore`: 12B 런타임 폴더와 작업 출력. `check_links.py`는 런타임 폴더를 건너뜀.

## 2026-10-20, 정정 (문서와 테스트)

10월 17\~20일 문서의 숫자를 기록과 다시 대조했습니다.

- 10월 20일 보고서와 README: 연결 거부와 서버 멈춤 조건의 요청 걸음 콜백은 0.004 s가 아니라 0.005 s.
  답을 기록한 걸음은 0.008\~0.019 s. 모델 대기가 10월 17일보다 짧은 주된 이유는 캐시가 아니라 짧은
  프롬프트이고, 캐시를 데운 시험 실행은 한 시간이 아니라 몇 분 앞이었음. 750걸음의 최대 |U|는 49.6 m/s.
  가장 빠른 셀은 한 셀에 머물지 않고 4 mm 움직였음. 전체 영역 그림의 범위는 x -1.55 \~ 0.60 m. 재생
  지연, 프롬프트 크기, 그림 한 장의 크기(프롬프트 토큰 약 106개, 270개가 아님)를 바로잡음. 인용 두 곳 수정.
- 10월 17일 보고서와 10월 19일 기록: Courant 근거를 잘못 말한 답은 그림 조건의 두 개. 10월 19일에는 좌표는
  같았지만 수치만 요청의 답과 재생 답 다섯 개의 문장이 달라졌음. RAM은 7.8 GiB.
- `make test`와 CI 테스트에 `test_async.py` 포함(70개). 그중 빠른 컴퓨터를 가정한 두 테스트가 CI에서
  실패해 고침. 분리된 워커 테스트는 답 파일이 써질 때까지 기다리고, sequence 테스트는 포크하는 걸음만
  엄격히 보고 늦은 답을 기다릴 수 있는 마지막 걸음은 뺌. 나머지 걸음 시간 상한은 0.5 s.
- `docs/evidence/2026-10-20/manifest.json`에 재생 폴더의 manifest 4개를 넣고, 출처 경로를 바로잡고,
  gzip 사본을 따로 표시.
- `llm_demo/README.md`에 10월 20일 기능(요청 모드, 비동기 요청, 저장한 프레임 재생, 새 환경 변수)을
  옮겨 적음. 공개된 프레임으로 재생 요청 24개가 바이트 단위로 다시 만들어짐. SVD 요약은 observe 요청에만 감.
- 첫 화면의 10월 20일 내용을 따로 떼어 10월 17일 내용 뒤로 옮기고, 코드와 실행 이름을 적음.
- 그림 해설 두 쪽(`guide.ko.html`, `overview.ko.html`)의 안내문: "비동기 처리는 아직 구현하지 않았다"를
  10월 20일 상태로 고침.

## 2026-10-20 (코드 `9449085`, 이 저장소의 `74553ea`)

- 비동기 요청(`LLM_ASYNC=1`): 요청 걸음은 워커를 포크하고 바로 복귀. 이후 걸음마다 막힘 없이
  확인해 도착 걸음을 기록하고, 늦은 워커는 종료하며, 대기 요청 수를 제한. 마지막 걸음에서
  남은 요청을 기다리거나 분리.
- 요청 모드: `describe`(그림 한 장, 설명과 가장 빠른 곳·가장 낮은 압력의 위치를 그린 범위의 %로),
  `sequence`(지정 걸음의 프레임을 모아 한 요청으로, 추세 단어).
- `LLM_IMAGE_XRANGE` / `LLM_IMAGE_YRANGE`로 영역 일부만 그림.
- `PythonAnalysis.H`가 `end_time_s`를 넘김.
- `run_async_cases.py`, `verify_async.py`(`POD_SUITE=async`), `snapshot_runner.py`,
  `test_async.py`(14개, 전체 70개).
- 실행: 3000걸음의 비동기 다섯 조건(`pod-llm-async.pp7agC`), 창 프레임(`pod-llm-async.8YC6bG`),
  describe·sequence 재생. 보고서: [docs/results-20261020.md](docs/results-20261020.md).

## 2026-10-19

- `CITATION.cff` 제거: 아직 인용할 논문이 없음. 용어 통일(시간 단계, 그림), 다음 단계에서 12B를 첫 항목으로.
- `test_callback.py`: 그림을 그리는 테스트의 콜백 마감을 4 s로. 공용 CI 러너에서 1 s는 모자랐음. 테스트만 바뀌고 솔버 코드는 그대로.
- 10월 17일 실행과 재생을 반복(`docs/evidence/2026-10-19/`): 해시, 그림 요청의 답, 재생 좌표 동일. 수치만 요청의 답과 재생 답 다섯 개의 문장은 달라짐.
- `llm_demo/hpc/`: GPU 노드에서 Gemma 4 12B로 같은 측정을 되풀이하는 스크립트와 Slurm 작업.
- NVIDIA A30에서 Gemma 4 12B QAT로 쌍별 재생(MedicineBow, Slurm 작업 24696203, 코드 `934da23`(영문
  저장소, 이 저장소의 `f4a99f3`)). 2026-10-20에 공개.
- 문서 구성 정리: 근거를 날짜별 폴더로, 영문 저장소에는 영문만 두고 한국어는 이 저장소로.
- CI: Python 3.10과 3.12에서 단위 테스트, 근거 파일을 manifest와 대조, 상대 링크 검사, 솔버 코드가 영문 저장소와 같은지 검사.
- 이 변경 기록, `Makefile`.
- README에 "5단계"의 뜻과 시험 컴퓨터 사양을 적음.

## 2026-10-18

- 10월 17일 보고서와 근거 공개. 릴리스 [korean-docs-2026-10-18](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18).

## 2026-10-17 (코드 `23089bb`)

- 다섯 조건 솔버 실행 `pod-llm-demo.LRfJBN`과 그림 유무 쌍 비교(`ablation_runner.py`). 단위 테스트 56개.
- 콜백 보강: 워커 절대 마감, 결과 파일은 별도 자식 프로세스가 기록, 클라이언트의 요청·응답 크기 제한.

## 2026-10-13 (코드 `9ae54d0`)

- PODFoam 안에서 그림을 보낸 첫 실행 `pod-llm-demo.SwwR2e`. 릴리스 [pod-insitu-demo-2026-10-13](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-demo-2026-10-13).
- PODFoam의 `analysis_func` 훅, 셀 다각형을 넘기는 `mesh_func`, `pod_image.py`, `bounded_ipc.py`, `llm_client.py`, 다섯 조건 실행기와 검증기.

## 2026-10-10

- OpenFOAM v2106에서 PODFoam 빌드, 연결 검증 `pod-v2106.c5jpOq` 통과(스냅샷·SVD 왕복). 로컬 모델에 수치만 보낸 첫 요청.

## 2026-10-08

- 과제 시작.
