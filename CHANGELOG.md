# 변경 기록

날짜는 실행이나 변경이 있었던 날입니다. 기록된 실행에는 그 실행을 만든 코드 버전을 적었습니다.

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
  모델 열한 개, 창 시드 세 개, 더 큰 이미지 토큰 한도의 무작위 창 시험(작업 24757344, 24757382~24757384);
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
  위치를 모른다고 함. 요청당 2.0~3.3 s.
- 10월 17일 보고서에 새 절, README에 12B 표. 12B를 시험하지 않았다는 문장을 바로잡음(README, 10월 20일
  보고서, `hpc/README.md`, 작업 기록). 첫 화면(`index.html`)에는 12B 절을 새로 넣음. 그림으로 보는 10월 17일 결과(`results-20261017.html`)와
  그림 해설 두 쪽(`guide.ko.html`, `overview.ko.html`)의 안내문에 12B 재생을 한 줄씩 더함.
- `hpc/README.md`: MedicineBow의 설정 줄과 llama.cpp 소스 빌드를 적은 "시험한 곳"(미리 빌드된 b11429
  라이브러리는 GLIBC_2.38이 필요). 12B 서버는 이미지 토큰 상한을 128로 낮춤.
- `replay_12b.slurm`, `demo_12b.slurm`: `HF_TOKEN`은 가중치를 내려받을 때만 필요. 계정과 파티션은
  `sbatch` 명령줄에서 줌. `setup_12b.sh`는 쓰고 있는 `llama-server`의 해시도 기록.
- `.gitignore`: 12B 런타임 폴더와 작업 출력. `check_links.py`는 런타임 폴더를 건너뜀.

## 2026-10-20, 정정 (문서와 테스트)

10월 17~20일 문서의 숫자를 기록과 다시 대조했습니다.

- 10월 20일 보고서와 README: 연결 거부와 서버 멈춤 조건의 요청 걸음 콜백은 0.004 s가 아니라 0.005 s.
  답을 기록한 걸음은 0.008~0.019 s. 모델 대기가 10월 17일보다 짧은 주된 이유는 캐시가 아니라 짧은
  프롬프트이고, 캐시를 데운 시험 실행은 한 시간이 아니라 몇 분 앞이었음. 750걸음의 최대 |U|는 49.6 m/s.
  가장 빠른 셀은 한 셀에 머물지 않고 4 mm 움직였음. 전체 영역 그림의 범위는 x -1.55 ~ 0.60 m. 재생
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
