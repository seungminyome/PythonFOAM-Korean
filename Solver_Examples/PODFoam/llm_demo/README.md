# PODFoam 계산 중 관찰·기록 기능

PODFoam은 선택한 계산 단계에서 속도·압력장의 수치 요약과 그림을 Gemma 4 E2B에 보냅니다. PythonFOAM의 콜백 함수가 전달을 맡고, llama.cpp가 로컬 CPU에서 모델을 실행합니다. 콜백은 정해진 형식의 답변을 저장한 뒤 솔버로 돌아옵니다. 모델의 답변은 U, p, 솔버 설정이나 제어 알고리즘을 바꾸는 데 사용하지 않습니다.

콜백은 동기식이거나 비동기식입니다. 동기식에서는 솔버가 답이나 마감을 기다립니다(10월 17일 측정). 비동기식(`LLM_ASYNC=1`)에서는 솔버가 계속 걸음을 진행하고, 답은 도착한 걸음과 함께 기록됩니다. 요청 모드는 셋입니다. `observe`는 수치와 같은 걸음의 그림을 보내는 원래 방식, `describe`는 그림 한 장의 설명과 극값의 위치, `sequence`는 실행 중 여러 장으로 본 흐름의 변화입니다. 결과는 [10월 17일 보고서](../../../docs/results.md), [10월 20일 보고서](../../../docs/results-20261020.md), [12B 쌍별 재생](../../../docs/results.md#gpu에서-gemma-4-12b로-같은-재생-2026-10-19), [10월 22일 그림 읽기 시험](../../../docs/results-20261022.md), [10월 22일 돌고 있는 솔버의 v2 그림](../../../docs/results-20261022-live.md), [10월 27일 변화 읽기·250걸음마다 요청·MPI](../../../docs/results-20261027.md)에 있습니다.

기존 PODFoam 예제에 선택적으로 사용할 수 있는 콜백을 추가했습니다. `snapshot_func`와 `svd_func`만 정의한 기존 모듈도 전과 같이 동작합니다.

## 솔버 안에서 호출되는 순서

시작할 때와 각 단계에서 부르는 함수입니다.

```
PythonCreate.H   startup    mesh_func(centres, volumes, solutionD, rank, cell polygons)   optional, once
PythonComm.H     each step  snapshot_func(U), svd_func(rank) at the SVD interval           as before
PythonAnalysis.H each step  analysis_func(state)                                           optional
```

`state`에는 해당 단계의 시간, 시간 간격 dt, `solverPerformanceDict`에서 가져온 잔차가 들어 있습니다. 잔차 기록은 Ux, Uy, p 각각의 첫 번째·마지막 초기 잔차, 최종 잔차, 선형 방정식 풀이 횟수와 반복 횟수입니다. 계산을 마친 단계의 `phi`로 다시 구한 Courant 수와 연속성 오차, 운동학적 압력의 복사본인 `p_cells`도 전달합니다. 같은 단계의 U는 이미 `snapshot_func`를 통해 전달된 상태입니다.

배열은 모두 복사본입니다. Python이 솔버의 원래 저장 공간을 직접 보지 않습니다. 병렬 실행에서는 격자와 필드를 마스터 rank로 모으고(`PythonGather.H`, 칸은 rank 순서), 마스터만 `mesh_func`와 `analysis_func`를 부릅니다. POD 스냅샷과 SVD는 전처럼 rank마다 따로 합니다. 2026-10-27에 rank 2개로 시험했습니다([보고서](../../../docs/results-20261027.md#mpi와-pod-파일)).

콜백 구현은 `llm_demo/python_module.py`에 있습니다. 선택한 한 단계(기본값 5)에서 별도 작업 프로세스를 만들어 다음 작업을 수행합니다.

1. 단계별 측정 기록을 저장하고, 그때까지 모은 스냅샷을 속도 성분별로 나누어 SVD 요약을 계산합니다.
2. `llm_observation/state.png`를 만듭니다. 크기는 640×360이며, 위에는 속력 |U|, 아래에는 p를 표시합니다. 2차원 사례에서는 C++가 `empty` 경계 패치의 면 정보를 넘겨주므로, 값을 보간하지 않고 각 셀을 다각형으로 그립니다. 그림에 사용한 배열은 `fields.npz`에 저장하고, 그 파일의 SHA-256 해시는 PNG 메타데이터에 넣습니다.
3. 요약과 PNG 데이터 URL을 `/v1/chat/completions`로 POST 요청합니다. 응답 형식에는 `observations`, `possible_interpretation`, `checks`라는 문자열 항목 3개가 필요합니다.
4. 요청 기록, 실제 HTTP 요청 본문, 원본 응답과 소요 시간을 저장합니다.

부모 프로세스는 메시지 길이를 표시한 파이프로 결과를 기다립니다. 전체 대기 기한은 `LLM_CALLBACK_DEADLINE_S`로 정하며 기본값은 120초입니다. 기한을 넘기면 작업 프로세스를 종료하도록 처리합니다. 부모가 결과 파일을 직접 쓰지는 않습니다. 별도의 짧게 실행되는 자식 프로세스가 0.2초의 시간 한도 안에서 최종 결과 파일을 씁니다. HTTP 클라이언트는 같은 컴퓨터의 루프백 주소만 허용하고 요청·응답 크기를 제한합니다. 연결, 응답 데이터가 오지 않는 시간, 전체 호출에 각각 시간 제한을 둡니다.

그림 생성에는 matplotlib이 필요합니다. 3차원 대체 방식인 최근접 셀 기반 래스터 그림에는 scipy도 필요합니다. matplotlib은 시작할 때 `mesh_func`에서 한 번 불러오며, 매 계산 단계에서 다시 불러오지 않습니다. `LLM_IMAGE_XRANGE="x0,x1"`(와 `LLM_IMAGE_YRANGE`)를 주면 그 창(단위 m)만 그립니다. 색 범위는 창 안의 셀로 정하고, 요청에 그린 범위를 적습니다.

## 요청 모드

| `LLM_MODE` | 보내는 것 | 묻는 것 | 답 항목 |
|---|---|---|---|
| `observe`(기본) | 수치 요약(+ 그림) | 관찰 | `observations`, `possible_interpretation`, `checks` |
| `describe` | 걸음, 시간, 그린 범위 + 그림 한 장 | 스냅샷 설명. 가장 빠른 곳과 가장 낮은 압력이 그린 x, y 범위의 몇 %에 있는지 | `flow_description`, `fastest_flow_x_percent`, `fastest_flow_y_percent`, `lowest_pressure_x_percent`, `lowest_pressure_y_percent`, `uncertainties` |
| `sequence` | 걸음과 시간 + 시간 순서의 그림 2~6장 | 첫 그림에서 마지막 그림까지 흐름이 어떻게 변하는지 | `change_description`, `max_speed_trend`, `min_pressure_trend`, `fastest_flow_region`, `uncertainties` |

`describe` 모드의 글에는 필드 값도 위치도 없습니다. 극값은 그림과 색 막대에서 읽어야 합니다. `sequence` 모드에서는 `LLM_SEQUENCE_STEPS`(예: `250,750,1250`)의 각 걸음에서 포크한 렌더러가 프레임을 그리고, 마지막 걸음에서 모든 프레임을 담은 요청 하나를 보냅니다. 앞 걸음의 프레임은 `llm_observation/step-XXXXXX/`에, 마지막 걸음의 프레임은 `llm_observation/` 자체에 저장됩니다.

추세 단어는 정해진 목록이라 답을 저장된 배열과 대조해 채점할 수 있습니다. 최고 속력은 `increasing`, `decreasing`, `roughly_constant`, `cannot_tell`, 최저 압력은 `more_negative`, `less_negative`, `roughly_constant`, `cannot_tell`, 가장 빠른 지점은 `same_place`, `moves`, `cannot_tell` 중 하나입니다. 답 형식은 서버가 강제하고(`response_format`, 정수 범위와 열거값이 있는 JSON 스키마) 클라이언트가 한 번 더 검사합니다.

## 비동기 요청

`LLM_ASYNC=1`이면 요청 걸음은 워커를 포크하고 바로 돌아옵니다(몇 밀리초). 이후 걸음마다 워커의 파이프를 막힘 없이 확인하고, 답이 오면 `arrived_at_step`과 함께 기록하며 솔버 로그에 `response_after` 표시를 남깁니다. 마감을 넘긴 워커는 같은 확인 과정에서 종료합니다. 동시에 진행하는 요청은 `LLM_ASYNC_MAX_PENDING`개(기본 1, 1~8)까지이고, 이를 넘는 요청은 건너뛰고 기록합니다. 마지막 걸음(솔버가 넘기는 `end_time_s`로 판단하며 `LLM_FINAL_STEP`으로 바꿀 수 있음)에 아직 답이 없으면 그 요청의 마감까지 기다리거나(`LLM_ASYNC_END=wait`, 기본) 그대로 두고 끝냅니다(`LLM_ASYNC_END=detach`. 이때도 워커가 `llm_response.json`을 직접 씁니다).

`POD_SUITE=async ./llm_demo/run_demo.sh`는 더 긴 실행에서 비동기 다섯 조건을 돌리고 `verify_async.py`로 검사합니다. 기본값은 `LLM_LONG_STEPS` 3000걸음, `LLM_LONG_DT` 5e-7 s, 필드와 SVD 모드 저장 간격 `LLM_LONG_WRITE` 250걸음, 요청 걸음 `LLM_LONG_STEP` 250, sequence 프레임 걸음 `LLM_LONG_SEQUENCE_STEPS` 250,750,1250입니다.

| 조건 | 모드 | 모델 요청 | 예상 결과 |
|---|---|---|---|
| `async-no-llm` | sequence | 사용 안 함(프레임은 그림) | 기준 필드와 프레임 |
| `async-describe` | describe | 사용 | `ok`, 솔버가 도는 동안 답 도착 |
| `async-sequence` | sequence | 사용 | `ok`, 프레임 셋을 한 요청에 |
| `async-server-error` | describe | 닫힌 포트 | `error`, 확인 과정에서 발견 |
| `async-timeout` | describe | 조금씩 응답하는 시험 서버 | `timeout`, 확인 과정에서 종료 |

`verify_async.py`는 저장된 모든 시각 폴더가 기준과 같은지, 프레임의 배열이 저장된 필드와 기준의 프레임과 같은지, 요청 걸음이 0.5 s 안에 끝났는지, 요청·도착·마지막 걸음을 뺀 모든 걸음이 1 s 안에 끝났는지, 답(또는 오류)이 도착 걸음과 함께 기록됐는지 확인합니다. sequence 조건에서는 요청 본문의 그림 해시도 확인합니다. `LLM_LONG_CASES=async-no-llm`은 기준 조건만 돌리므로 모델 요청 없이 프레임을 얻는 방법입니다. 다만 실행기가 첫 조건 전에 서버를 확인하므로 모델을 띄운 llama-server는 있어야 합니다.

## 솔버가 그리는 v2 그림 (`LLM_IMAGE_STYLE=v2`)

`LLM_IMAGE_STYLE=v2`이면 `describe`와 `sequence` 요청이 `state.png` 대신 2026-10-22 그림 읽기 시험의 그림을 보냅니다. 필드마다 1024×576 PNG 한 장(|U|, 그다음 p), 두 축은 그린 범위의 퍼센트이고 10 %마다 격자선이 있으며, 색 막대에는 값 다섯 개를 적습니다(`readable_image.py`). 기본값은 `v1`이고, 이때 솔버는 2026-10-13~2026-10-20의 동작을 바이트까지 그대로 지킵니다. `observe`는 언제나 v1 그림을 보내고, `observe`에 v2를 주면 거부합니다.

- v2 프레임은 모두 `llm_observation/step-NNNNNN/` 폴더 하나이고, 안에 `fields.npz`, `U.png`, `p.png`, 그리고 마지막에 쓰는 `readable-metadata.json`이 있습니다. 요청 걸음의 프레임도 같습니다. 폴더가 이미 있으면(같은 경우 폴더에서 다시 돌린 경우. 걸음 번호는 솔버 프로세스마다 처음부터 다시 셉니다) 덮어쓰지도 보내지도 않고, 그 프레임 저장이나 요청을 거부합니다.
- 요청은 그림 시험과 같은 함수로 `readable_request.py`가 만듭니다. `describe_v2_payload`, 그리고 sequence에는 그림마다 제 색 범위를 쓰는(v2own 프롬프트) `sequence_v2_payload`입니다. v2 sequence는 두세 걸음(그림 최대 여섯 장)을 받습니다. 요청에는 언제나 `max_tokens` 320, 시드 20261021, `cache_prompt: false`가 들어가므로 `LLM_MAX_TOKENS`는 비워 두거나 320이어야 합니다. `test_picture_test.GoldenV2RequestTests`는 발표된 2026-10-22 요청의 바이트를 고정하고, `verify_async.py`는 실시간 본문이 디스크의 프레임에 빌더를 적용한 결과와 바이트까지 같은지 확인합니다.
- v2 describe 요청은 SVD 요약을 보내지 않으므로, 콜백은 스냅샷 창을 쌓지도 계산하지도 않습니다. 그래서 긴 실행의 늦은 걸음에 요청해도 워커가 느려지지 않습니다.
- 그린 범위는 `LLM_IMAGE_XRANGE`/`LLM_IMAGE_YRANGE`, 없으면 전체 영역입니다. v2는 x-y 평면의 2차원 경우이고 칸마다 다각형 하나가 있어야 합니다(래스터 대체 없음).
- 서버 컨텍스트는 그림 시험처럼 4096토큰, batch/ubatch 512로 하세요. 세 시각 v2 sequence는 프롬프트가 약 2,200토큰입니다.

`LLM_KILL_JOIN_S`(기본 0.1 s, 2026-10-27 전에는 0.02 s; 최대 2 s)는 끊은 워커를 거두는 데 기다리는 시간입니다. 자식 프로세스가 쓰는 메모리가 클수록 오래 걸립니다. MedicineBow 노드에서는 200 MB에 약 16 ms, 500 MB에 38 ms였고, 0.5 GB 솔버에서 포크한 워커는 0.02 s 안에 거둬지지 않습니다. 그래서 그곳 작업은 0.2 s를 씁니다.

### 발달한 흐름에서 시작하기

`LLM_LONG_START=<시각 폴더>`이면 비동기 시험의 모든 경우가 t = 0 대신, 같은 격자(격자 파일을 해시로 비교)로 돌린 이전 실행의 그 상태에서 시작합니다. 그 필드를 복사하고, 시간 번호가 처음부터 다시 시작하도록 `uniform/`은 빼며, 끝 시각은 시작 시각에 `LLM_LONG_STEPS` × `LLM_LONG_DT`를 더한 값입니다. 콜백의 걸음 번호는 시작부터 셉니다. `LLM_LONG_FIXTURE_DEADLINE_S`(기본 4)는 연결 거부와 멈춤 경우의 콜백 마감입니다. 이런 실행에서 `verify_async.py`는 모든 경우의 시작 파일이 기록된 것과 같은지, Courant 수가 1보다 작은지도 확인합니다.

### 한 연구에서 describe 요청 여러 개 (`run_live_sweep.py`)

비동기 시험은 창 하나에 describe 요청 하나를 보냅니다. 창이 고정이면 답이 늘 비슷한 자리에 있어서, 답 하나로 고정해도 잘 맞습니다. `run_live_sweep.py <시험 실행> <PODFoam> <출력>`은 v2 시험 뒤에 요청 걸음 R마다(기본 500걸음마다) 경우를 하나씩 더 돌립니다. 모두 같은 시작 상태에서 출발하고, R에서의 기준 저장 상태의 가장 빠른 칸 둘레에 무작위로 놓은 창(`window_test.py`의 규칙)으로 R에 describe 요청을 보냅니다. 답이 솔버가 도는 동안 왔는지, 요청 본문이 시험한 빌더를 프레임에 적용한 결과인지, 프레임의 배열이 R에서 기준이 쓴 필드와 같은지 확인하고, 답과, 모든 답에 대해 가장 잘 맞는 고정 답 하나를 채점합니다(`sweep-summary.json`).

### N걸음마다 요청 (`LLM_ANALYSIS_EVERY`)

`LLM_ANALYSIS_EVERY=N`(v2 그림의 describe)이면 `LLM_ANALYSIS_STEP`에서, 그 뒤 N걸음마다 describe 요청을 보냅니다. 대기 중인 요청이 `LLM_ASYNC_MAX_PENDING`보다 적을 때만 보내고, 한도에 걸린 걸음은 건너뛰고 기록합니다. 요청마다 늘 쓰는 파일(`llm_request.json`, `llm_request_body.json`, `llm_response.json`, `llm_result.json`, 원래 답)을 자기 폴더 `llm_requests/step-NNNNNN/`에 쓰고, 마지막 걸음에서 `llm_requests/index.json`(걸음, 상태, 도착 걸음, 모델 시간, 솔버 멈춤)을 씁니다. `run_periodic.py <시험 실행> <PODFoam> <출력>`은 v2 시험의 기준 준비 폴더에서 이런 경우 하나와 요청 없는 쌍둥이를 돌려 저장 파일을 모두 비교하고, 요청 본문을 빌더와, 프레임을 저장 필드와 대조하고, 답을 채점하고, 걸린 시간, 메모리(솔버 프로세스들의 RSS와 PSS, 0.5 s마다), 요청마다 워커 파이프로 오간 바이트(결과의 `ipc_bytes_received`)를 기록합니다. `hpc/periodic_v2.slurm`이 GPU 노드에서 돌립니다.

### 발달한 흐름의 변화 읽기 시험 (`sequence_test.py`)

`sequence_test.py build --states <경우> --centres <fields.npz> --old-manifest ... --output <묶음>`은 저장 상태 세 개씩(기본 간격 2000, 4000, 6000걸음)을 묶고, 묶음마다 가장 빠른 칸들 둘레에 무작위 창 하나를 놓고(위의 창 규칙, 가장 빠른 칸이 모두 여백 안쪽), 정답의 (속력 추세, 압력 추세) 아홉 가지가 상태가 허락하는 만큼 고르게 차도록 `--count`개를 고릅니다. 같은 세 시각 묶음으로 다섯 가지를 만듭니다. `dev-sequence-v1`(솔버의 두 칸 그림, 2026-10-20 프롬프트), `dev-sequence-v2own`(필드 하나씩 그린 그림, 그림마다 자기 색 범위, 2026-10-22 프롬프트), `dev-sequence-v2own-t`(같은 것에 정답의 기준을 프롬프트에 적음: 추세는 2 %, 자리는 그린 범위의 5 %), `dev-sequence-v2own-tn`(여기에 시각마다 배열에서 구한 최대 |U|와 최소 p를 메모에 더함), `dev-sequence-numbers`(그 메모와 가장 빠른 칸의 위치만, 그림 없음). `readable_request.sequence_v2_payload(..., thresholds=True, numbers=..., images=False)`가 만들며, 기본값이면 2026-10-22 본문을 바이트까지 그대로 줍니다. `--dt`(여기와 `window_test.py`)는 상태 이름을 나눌 시간 간격으로, 다른 간격으로 돈 실행에 씁니다. `--y-span`은 창 높이의 범위(m)입니다. 2026-10-27에 돌렸습니다([보고서](../../../docs/results-20261027.md#스냅샷-사이의-변화-읽기)).

### 무작위 창 그림 시험 (`window_test.py`)

`window_test.py build`는 한 실행의 저장 상태(어떤 시각 폴더든; `--first-step`, `--describe-every`, `--last-step`은 5e-7 s 걸음 단위)를 상태마다 여러 번 그리면서, 그린 범위를 가장 빠른 칸 둘레에 무작위로 놓습니다. 그 칸은 모든 가장자리에서 15 % 이상 떨어지고, 안에 칸이 200개 이상 있고, 높이 0.03~0.114 m, 너비는 높이의 1.5~4배입니다. `flow-window-v1`과 `flow-window-v2` 묶음을 쓰고, `check`, `run`, `report`는 `picture_test.py`처럼 동작하며, 고정 답 점수는 묶음 전체에 답 하나로 셉니다. `hpc/window_test.slurm`이 GPU 노드에서 묶음 하나를 돌립니다.

## 저장한 프레임 재생 (describe, sequence)

`snapshot_runner.py`는 저장한 프레임(`state.png`, `fields.npz`, `image-metadata.json`이 있는 폴더)을 describe나 sequence 프롬프트로 보내고 답을 배열과 대조해 채점합니다.

```bash
python3 snapshot_runner.py --mode describe --frames RUN/async-no-llm/llm_observation/step-000250 \
    RUN/async-no-llm/llm_observation/step-000750 RUN/async-no-llm/llm_observation \
    --output /tmp/describe-replay --repeats 3 --execute
python3 snapshot_runner.py --mode sequence --frames RUN/async-no-llm/llm_observation/step-000250 \
    RUN/async-no-llm/llm_observation/step-000750 RUN/async-no-llm/llm_observation \
    --output /tmp/sequence-replay --repeats 3 --execute
```

`RUN`은 `pod-llm-async.XXXXXX` 폴더입니다. 공개된 프레임(전체 영역은 `docs/evidence/2026-10-20/pod-llm-async.pp7agC`, 창은 `pod-llm-async.8YC6bG`의 `step-000250`, `step-001250`, `llm_observation`)을 주면 10월 20일 재생 요청 24개가 바이트 단위로 똑같이 다시 만들어집니다(기본값: 첫 반복의 시드 20261020, 반복마다 1씩 증가, `--max-tokens` 320). `--execute`를 빼면 요청과 기준값만 만들고 서버에는 보내지 않습니다.

describe의 점수는 답한 % 위치와, 그린 창 안에서 최대 속력(과 최저 압력)을 가진 실제 셀 사이의 거리입니다. 그린 범위의 %와 m로 적습니다. sequence에서는 답한 추세 단어를 저장된 극값의 추세와 비교합니다. 상대 변화가 2 %를 넘으면 추세로 보고, 가장 빠른 지점이 그린 범위의 5 %보다 많이 움직이면 "moves"입니다. 기준값은 `ground_truth.private.json`에 쓰고 모델에는 보내지 않습니다.

## 그림 읽기 시험 (모델 여러 개, 그림 두 가지)

`picture_test.py`는 저장한 그림에 대해 정해 둔 요청 묶음을 만들고, 서버 하나에 보내고, 모델이 보지
못한 정답과 비교해 채점합니다. 그림은 두 가지입니다. v1은 콜백이 그리는 그림(`pod_image.py`)이고, v2는
`readable_image.py`가 그립니다(그림 한 장에 필드 하나, 축은 퍼센트와 10 %마다 격자선, 색 막대에
최솟값부터 최댓값까지 값 다섯 개). `foam_fields.py`는 저장한 OpenFOAM 상태를 읽습니다(ASCII만).

```bash
# 저장소 루트에서. --states는 모델 요청 없이 돌린 PODFoam 사례
# (2026-10-21 묶음의 인자, 요청 308개. --sequence가 없으면 flow-sequence 묶음은 만들지 않음)
python3 Solver_Examples/PODFoam/llm_demo/picture_test.py build --states <사례> \
    --centres docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz \
    --oct17 docs/evidence/2026-10-17/ablation --oct20 docs/evidence/2026-10-20/replay \
    --describe-every 500 --last-step 6000 \
    --sequence 250,750,1250 --sequence 250,1250,2750 --sequence 1250,2250,3250 \
    --sequence 2250,3250,4250 --sequence 3250,4250,5250 --sequence 4500,5250,6000 \
    --sequence 5000,5500,6000 --output <시험 묶음>              # matplotlib 필요
cd Solver_Examples/PODFoam/llm_demo
python3 picture_test.py check --test-set <시험 묶음>       # 모든 요청과 정답을 manifest와 대조
python3 picture_test.py run --test-set <시험 묶음> --model <서버 이름> --endpoint <url> --output <실행 폴더>
python3 picture_test.py report <실행 폴더> [<실행 폴더> ...] --output report.md
```

2026-10-21에 만든 묶음의 인자는
[manifest](../../../docs/evidence/2026-10-22-picture-test/test-set/manifest.json)의 `build_args`에 있습니다.
2026-10-21의 묶음과 그 묶음을 만드는 법, 모델 일곱 개로 돌린 클러스터 작업은
[hpc/README.md](hpc/README.md#그림-읽기-시험-2026-10-22-실행)에, 결과는
[10월 22일 보고서](../../../docs/results-20261022.md)에 있습니다.

## 실행 방법

OpenFOAM v2106, numpy와 matplotlib이 설치된 Python 3, [C++·Python 연결 검증](../validation/README.md)을 통과한 실행 자료가 필요합니다. 통과한 실행 자료는 기준 사례로 사용합니다. 모델 파일에는 약 3.4 GB의 디스크 공간이 필요하고, 서버는 실행 중 약 2.4 GiB(10월 20일 기록)를 쓰므로 RAM 8 GB 정도면 됩니다.

```bash
cd Solver_Examples/PODFoam
./llm_demo/setup_runtime.sh            # downloads model, projector, llama.cpp b11429; checks SHA-256
python3 llm_demo/runtime.py start      # loads the model once; later runs reuse it
python3 llm_demo/runtime.py standalone # optional: one request with a synthetic plot
./llm_demo/run_demo.sh                 # builds PODFoam, runs the cases, verifies
python3 llm_demo/runtime.py stop       # when the server is no longer needed
```

사용할 수 있는 환경 변수는 다음과 같습니다.

- `OPENFOAM_BASHRC`, `PYTHON`, `POD_WORKSPACE`
- `POD_LLM_RUNTIME`: 모델 폴더. 기본값은 저장소 작업 폴더 옆의 `../llm-runtime`
- `POD_LLM_PORT`: 기본 포트 8088
- `POD_REFERENCE_RUN`: 기준 실행 자료. 기본값은 검증을 통과한 가장 최근 실행
- `LLM_ANALYSIS_STEP`, `LLM_IMAGE_INPUT`(1/0)
- `LLM_CALLBACK_DEADLINE_S`, `LLM_CONNECT_TIMEOUT_S`, `LLM_READ_TIMEOUT_S`
- `LLM_MAX_TOKENS`: `observe`는 최대 192, 다른 모드는 최대 320
- `LLM_MODE`: `observe`(기본), `describe`, `sequence`
- `LLM_ASYNC`: `1`이면 비동기(기본 `0`)
- `LLM_SEQUENCE_STEPS`: sequence 프레임을 그릴 걸음 2~6개(예: `250,750,1250`)
- `LLM_ASYNC_MAX_PENDING`: 동시에 진행하는 요청 수, 기본 1(1~8)
- `LLM_ASYNC_END`: 마지막 걸음에서 `wait`(기본) 또는 `detach`
- `LLM_FINAL_STEP`: 마지막 걸음을 직접 지정(기본은 솔버가 넘기는 `end_time_s`로 판단)
- `LLM_IMAGE_XRANGE`, `LLM_IMAGE_YRANGE`: 그릴 창 `"x0,x1"`(m)
- `POD_SUITE`: `async`이면 긴 비동기 다섯 조건(기본 `sync`)
- `LLM_LONG_STEPS`, `LLM_LONG_DT`, `LLM_LONG_WRITE`, `LLM_LONG_STEP`, `LLM_LONG_SEQUENCE_STEPS`, `LLM_LONG_CASES`: 비동기 다섯 조건의 설정

`run_demo.sh`는 따로 정하지 않으면 모든 모드에 `LLM_MAX_TOKENS=192`를 설정합니다. 그래서 10월 20일 솔버 안의 describe·sequence 요청은 192였고, 재생은 320이었습니다. 실행기는 일부 변수를 조건마다 직접 정합니다. 동기 실행기는 `LLM_ENABLED`와 `LLM_IMAGE_INPUT`을 정하고, `LLM_ANALYSIS_STEP`은 환경 값(기본 5)을 그대로 넘깁니다. 비동기 실행기는 `LLM_ENABLED`, `LLM_IMAGE_INPUT`(항상 1), `LLM_ASYNC`, `LLM_MODE`, `LLM_ANALYSIS_STEP`(`LLM_LONG_STEP` 값), `LLM_SEQUENCE_STEPS`(`LLM_LONG_SEQUENCE_STEPS` 값)를 정하고 `LLM_FINAL_STEP`은 무시하므로, 비동기 다섯 조건은 `LLM_LONG_*` 변수로 설정하세요.

`run_cases.py`는 `LLM_ENDPOINT` 뒤의 서버가 `$POD_LLM_RUNTIME/server.pid`에
기록된 프로세스인지 확인합니다. 서버를 다른 런타임 폴더에서 띄웠다면
`POD_LLM_RUNTIME`을 그 폴더로 지정하세요.

클러스터 GPU에서 Gemma 4 12B로 같은 측정을 되풀이하려면
[hpc/README.md](hpc/README.md)를 보세요. 쌍별 재생은 이 방법으로 NVIDIA A30에서 돌려
보았습니다([기록](../../../docs/evidence/2026-10-19-12b/README.md)).

`run_demo.sh`는 작업 공간의 `llm-demo-work/bin/`에 솔버를 빌드하고, `pod-llm-demo.XXXXXX` 폴더를 만든 뒤 아래 5개 사례를 각각 10단계씩 실행합니다.

| 사례 | 모델 요청 | 그림 | 예상 결과 |
|---|---|---|---|
| `fixed-pod-no-llm` | 사용 안 함 | 생성만 하고 보내지 않음 | 기준 결과 필드 |
| `fixed-pod` | 사용 | 요청에 첨부 | `ok` |
| `fixed-pod-text-only` | 사용 | 첨부하지 않음 | `ok` |
| `fixed-pod-server-error` | 닫힌 포트로 요청 시도 | 요청에 첨부 | `error`, 기한 4초 |
| `fixed-pod-timeout` | 조금씩 응답하는 시험 서버로 요청 | 요청에 첨부 | `timeout`, 기한 4초 |

`verify_demo.py`는 단계별 기록의 잔차·Courant 수·연속성 오차가 솔버 로그와 맞는지, 콜백이 6단계 전에 마감과 정리 여유 안에 돌아왔는지, 저장된 필드 파일 45개가 기준 실행과 같은지 확인합니다.

그림을 사용하는 사례에서는 `fields.npz`가 `5e-07/U`와 `p`에 맞는지, PNG가 요청에 실제로 들어간 그림과 같은지, 요청 문장이 저장된 요약과 같은지도 확인합니다. 모든 검사를 통과하면 `PASS`를 출력합니다.

이어서 `pack_run.py`가 소스, 실행 기록, 요청과 답을 중간 시각 없이 `run-archive.tar.gz`로 묶습니다. 10월 17일 전체 실행은 [릴리스 파일](../../../docs/evidence/2026-10-17/README.md#전체-실행)입니다.

모델 없이 단위 테스트를 실행하려면 다음 명령을 사용합니다.

```bash
cd Solver_Examples/PODFoam/llm_demo
python3 -m unittest test_llm_client test_callback test_ablation_runner test_async -v
```

## 저장한 상태를 그림 있이, 없이 다시 보내기

데모의 두 정상 요청은 프롬프트가 달라서 그림이 무엇을 더해 주는지 말해 주지 못합니다. `ablation_runner.py`는 저장된 한 단계로 PNG만 다른 요청 두 개를 보냅니다.

| 조건 | 질문과 수치 요약 | PNG |
|---|---|---|
| `numeric_only` | 동일하게 고정한 문장 | 제외 |
| `numeric_plus_image` | 동일하게 고정한 문장 | 포함 |

한 쌍 안에서 지시문, 모델, 시드, 생성 설정은 같습니다. 두 조건 모두 요약에 적힌 그림의 값 범위와 영역 크기를 받습니다. 최대 속력의 실제 위치는 저장된 배열에서 구해 채점에만 씁니다. 요청을 만들기 전에 PNG, 메타데이터, 배열, 요약이 서로 맞는지 확인합니다.

공개된 10월 17일 스냅샷으로 요청만 만들어 보기(`llm_demo`에서, 서버 접속 없음):

```bash
python3 ablation_runner.py \
  --case ../../../docs/evidence/2026-10-17/pod-llm-demo.LRfJBN/fixed-pod \
  --output /tmp/pod-ablation-preview \
  --repeats 3 --seed 20261017
```

출력 폴더는 매번 새로 쓰세요. 어느 실행의 `fixed-pod` 폴더든 `--case`로 줄 수 있습니다. 서버가 떠 있으면 세 쌍을 실제로 보냅니다:

```bash
python3 ablation_runner.py \
  --case ../../../docs/evidence/2026-10-17/pod-llm-demo.LRfJBN/fixed-pod \
  --output /tmp/pod-ablation-measured \
  --repeats 3 --seed 20261017 --timeout-s 120 --execute
```

10월 17일의 [manifest](../../../docs/evidence/2026-10-17/ablation/manifest.json)에 원래 요청과 순서가 있습니다(시드 20261017, 20261018, 20261019, 쌍마다 먼저 보내는 조건을 번갈아 바꿈). 10월 19일 12B 재생은 같은 요청에서 `model`만 바꿨습니다. 서버 빌드, 가중치, 프로젝터, 스레드 수, 문맥 길이는 실행 사이에 고정하고 `--server-note`로 적어 두세요.

요청마다 본문, 답, 해시, 상태, 측정값을 저장합니다.

- **위치:** x만 답하면 x축 오차를, 두 축을 답하면 그 평면에 투영한 거리를, 세 축을 모두 답하면 3차원 거리를 계산합니다. 좌표가 없거나 뜻이 모호하면 점수를 매기지 않습니다. 요약에는 채점할 수 있었던 답변의 비율도 기록합니다.
- **주장 검사:** 규칙 몇 개가 잘못 인용한 숫자와 근거 없는 단정을 찾습니다. 많이 놓칩니다. 10월 17일 [답 검토](../../../docs/evidence/2026-10-17/independent-ablation-review.json)에 놓친 것이 적혀 있으니 답도 직접 읽으세요.
- **시간:** `replay_callback_wall_s`는 준비된 요청을 보내고, 기다리고, 평가하고, 저장하는 시간을 측정합니다. HTTP 요청과 응답을 기다린 시간도 따로 기록합니다. 이 재생 시험은 솔버, SVD, 그림 생성을 다시 실행하지 않습니다. 같은 실행의 솔버 로그가 있으면 `original_cpp_callback_wall_s`에 당시 콜백 시간을 별도로 기록합니다.

재생은 모델을 시험하는 것이지 솔버 연결을 시험하는 것이 아닙니다. 연결은 다섯 조건 데모와 `verify_demo.py`로 확인하세요.

## 이전 실행 (10월 13일)

`pod-llm-demo.SwwR2e`(솔버 버전 `9ae54d0`)의 측정값과 답변은 [10월 13일 보고서](../../../docs/results-20261013.md)와 [근거 자료](../../../docs/evidence/2026-10-13/README.md)에 있습니다. 당시 그림 요청과 수치만 요청은 지시문이 달라서 그림의 효과를 분리하지 못했습니다. 그 역할은 10월 17일의 재생 비교가 합니다.

## SVD 요약의 의미

observe 요청(그림 있이, 없이)은 그때까지 모은 속도 스냅샷의 성분별 SVD 요약을 받습니다. 특이값과 그 비율만 보내고 공간 모드는 보내지 않습니다. describe와 sequence 요청에는 SVD 요약이 없습니다. `leading_energy_fraction`은 σ₁²를 특이값 제곱의 합으로 나눈 값, 즉 첫 패턴이 스냅샷 행렬에서 차지하는 몫입니다(10월 17일과 19일 실행의 5단계 Ux에서 99.997 %). 행렬은 평균을 빼지 않았고 가중치도 없습니다. 자료 요약일 뿐 물리적 에너지도 정확도 척도도 아니며, 모델에 도움이 되는지는 시험하지 않았습니다.

정상 요청의 작업 프로세스 기한은 120초입니다. 일부러 실패시키는 조건에는 4초 기한과 정리 시간을 포함한 4.27초의 허용 한도를 적용합니다.

[그림을 곁들인 한국어 해설](../../../docs/guide.ko.html) · [영문 원문](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/PODFoam/llm_demo/README.md)
