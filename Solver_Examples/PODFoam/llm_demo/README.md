# PODFoam 계산 중 관찰·기록 기능

PODFoam은 선택한 계산 단계에서 속도·압력장의 수치 요약과 그림을 Gemma 4 E2B에 보냅니다. PythonFOAM의 콜백 함수가 전달을 맡고, llama.cpp가 로컬 CPU에서 모델을 실행합니다. 콜백은 정해진 형식의 답변을 저장한 뒤 솔버로 돌아옵니다. 모델의 답변은 U, p, 솔버 설정이나 제어 알고리즘을 바꾸는 데 사용하지 않습니다.

콜백은 동기식이거나 비동기식입니다. 동기식에서는 솔버가 답이나 마감을 기다립니다(10월 17일 측정). 비동기식(`LLM_ASYNC=1`)에서는 솔버가 계속 걸음을 진행하고, 답은 도착한 걸음과 함께 기록됩니다. 요청 모드는 셋입니다. `observe`는 수치와 같은 걸음의 그림을 보내는 원래 방식, `describe`는 그림 한 장의 설명과 극값의 위치, `sequence`는 실행 중 여러 장으로 본 흐름의 변화입니다. 결과는 [10월 17일 보고서](../../../docs/results.md), [10월 20일 보고서](../../../docs/results-20261020.md), [12B 쌍별 재생](../../../docs/results.md#gpu에서-gemma-4-12b로-같은-재생-2026-10-19), [10월 22일 그림 읽기 시험](../../../docs/results-20261022.md), [10월 22일 돌고 있는 솔버의 v2 그림](../../../docs/results-20261022-live.md), [10월 27일 변화 읽기·250걸음마다 요청·MPI](../../../docs/results-20261027.md)에 있습니다.

기존 PODFoam 예제에 선택적으로 사용할 수 있는 콜백을 추가했습니다. `snapshot_func`와 `svd_func`만 정의한 기존 모듈도 전과 같이 동작합니다.

## 솔버 안에서 호출되는 순서

시작할 때와 각 단계에서 부르는 함수입니다.

```
PythonCreate.H   startup    mesh_func(centres, volumes, solutionD, rank, cell polygons[, slice plane])   optional, once
PythonComm.H     each step  snapshot_func(U), svd_func(rank) at the SVD interval                         as before
PythonAnalysis.H each step  analysis_func(state)                                                         optional
```

`state`에는 해당 단계의 시간, 시간 간격 dt, `solverPerformanceDict`에서 가져온 잔차가 들어 있습니다. 잔차 기록은 Ux, Uy, p 각각의 첫 번째·마지막 초기 잔차, 최종 잔차, 선형 방정식 풀이 횟수와 반복 횟수입니다. 계산을 마친 단계의 `phi`로 다시 구한 Courant 수와 연속성 오차, 운동학적 압력의 복사본인 `p_cells`도 전달합니다. 같은 단계의 U는 이미 `snapshot_func`를 통해 전달된 상태입니다.

배열은 모두 복사본입니다. Python이 솔버의 원래 저장 공간을 직접 보지 않습니다. 병렬 실행에서는 격자와 필드를 마스터 rank로 모으고(`PythonGather.H`, 칸은 rank 순서), 마스터만 `mesh_func`와 `analysis_func`를 부릅니다. POD 스냅샷과 SVD는 전처럼 rank마다 따로 합니다. 2026-10-27에 rank 2개로 시험했습니다([보고서](../../../docs/results-20261027.md#mpi와-pod-파일)).

3차원 경우(2026-10-28). 3차원 격자에는 `empty` 패치가 없으므로, 칸 다각형은 대신 평면 단면에서 얻습니다(`PythonSlice.H`). OpenFOAM의 `cuttingPlane`을 z = `LLM_SLICE_Z`(기본값: 격자 z 범위의 가운데)에 두고, 법선은 (0 0 1)이며, 삼각형으로 나누지 않으므로 잘린 칸마다 다각형 하나, 곧 그 칸의 단면이 나옵니다. 격자점을 지나는 평면(고른 층이 짝수 개일 때의 가운데)은 두 칸 사이의 면 위에 놓이게 되므로, 위쪽 다음 점 평면까지의 절반만큼 옮깁니다. 다각형은 같은 세 인자로, 같은 rank별 칸 오프셋과 모으기를 거쳐 넘어가고, 여덟 번째 인자가 평면을 설명합니다. 2차원 경우는 전처럼 인자 일곱 개로 부릅니다. 그러면 v2 그림은 단면 칸만, 저마다 제 색을 칠한 다각형 하나로 그리고, v2 프레임에는 그 칸만 들어갑니다. `fields.npz`에는 그 칸들의 중심(3차원 칸 중심), U, p, 그리고 `mesh_cells`, `polygon_points`, `polygon_offsets`가 있고, `readable-metadata.json`에는 `slice`(z, 요청한 z, 그 값의 출처, 옮겼는지, 단면과 격자의 칸 수)가 들어갑니다. 요청은 2차원과 같이 만들고, 그림도 요청도 단면을 보여 준다고 말하지 않습니다. 읽을 수 없는 `LLM_SLICE_Z`나 아무 칸도 자르지 않는 평면이면 솔버는 계속 돌고 v2 요청은 이유와 함께 거부되며, `pod_image.plane_slice`의 검사를 통과하지 못한 단면 다각형도 마찬가지입니다. 3차원 경우의 v1 그림은 모든 칸의 최근접 칸 래스터를 그대로 씁니다. 단면은 평면으로 보간한 값이 아니라 잘린 칸 자신의 U와 p(|U|에는 Uz가 들어감)를 보여 줍니다. 시험 경우에서 `LLM_SLICE_Z=0.002`이면 잘린 칸의 중심은 z = 0.00238 m에 있습니다. 3차원 경우에는 2026-10-28 이후의 `python_module.py`가 필요합니다. 예전 `mesh_func`는 인자 일곱 개를 받으므로 여덟 번째에서 실패하고, 그 경우는 그림 없이 남습니다. 쐐기(축대칭) 격자와, symmetry나 cyclic 패치로 둘러싸인 한 층짜리 격자에도 `empty` 패치가 없으므로 z 가운데에서 잘리게 되는데, 시도하지 않았습니다. z 방향으로 칸 8개만큼 늘인 계단 경우에서 직렬과 rank 2개로 시험했고([근거 자료](../../../docs/evidence/2026-10-28-3d/README.md)), 다른 3차원 격자나 모델로는 시험하지 않았습니다.

콜백 구현은 `llm_demo/python_module.py`에 있습니다. 선택한 한 단계(기본값 5)에서 별도 작업 프로세스를 만들어 다음 작업을 수행합니다.

1. 그때까지 모은 스냅샷을 속도 성분별로 나누어 SVD 요약을 계산합니다(2026-10-27까지는 작업 프로세스가 여기서 `telemetry.jsonl`도 다시 썼습니다. [아래](#telemetryjsonl)를 보십시오).
2. `llm_observation/state.png`를 만듭니다. 크기는 640×360이며, 위에는 속력 |U|, 아래에는 p를 표시합니다. 2차원 사례에서는 C++가 `empty` 경계 패치의 면 정보를 넘겨주므로, 값을 보간하지 않고 각 셀을 다각형으로 그립니다. 그림에 사용한 배열은 `fields.npz`에 저장하고, 그 파일의 SHA-256 해시는 PNG 메타데이터에 넣습니다.
3. 요약과 PNG 데이터 URL을 `/v1/chat/completions`로 POST 요청합니다. 응답 형식에는 `observations`, `possible_interpretation`, `checks`라는 문자열 항목 3개가 필요합니다.
4. 요청 기록, 실제 HTTP 요청 본문, 원본 응답과 소요 시간을 저장합니다.

부모 프로세스는 메시지 길이를 표시한 파이프로 결과를 기다립니다. 전체 대기 기한은 `LLM_CALLBACK_DEADLINE_S`로 정하며 기본값은 120초입니다. 기한을 넘기면 작업 프로세스를 종료하도록 처리합니다. 부모가 결과 파일을 직접 쓰지는 않습니다. 별도의 짧게 실행되는 자식 프로세스가 0.2초의 시간 한도 안에서 최종 결과 파일을 씁니다. HTTP 클라이언트는 같은 컴퓨터의 루프백 주소만 허용하고 요청·응답 크기를 제한합니다. 연결, 응답 데이터가 오지 않는 시간, 전체 호출에 각각 시간 제한을 둡니다.

그림 생성에는 matplotlib이 필요합니다. v1의 3차원 대체 방식인 최근접 셀 기반 래스터 그림에는 scipy도 필요합니다. matplotlib은 시작할 때 `mesh_func`에서 한 번 불러오며, 매 계산 단계에서 다시 불러오지 않습니다. `LLM_IMAGE_XRANGE="x0,x1"`(와 `LLM_IMAGE_YRANGE`)를 주면 그 창(단위 m)만 그립니다. 색 범위는 창 안의 셀로 정하고, 요청에 그린 범위를 적습니다.

### telemetry.jsonl

`telemetry.jsonl`에는 걸음마다 한 줄이 있습니다. 솔버가 넘긴 상태(`p_cells`와 `u_cells` 제외), `null`로 적고 `feature_issues`에 나열한 유한하지 않은 값, 그리고 `run_id`입니다. 2026-10-28부터 콜백은 걸음이 오면 그 걸음의 줄을 인코딩하고, 아직 디스크에 없는 줄만 들고 있습니다. 마감(0.2 s, 또는 대기 중인 줄마다 1e-4 s로 셈한 값이 더 크면 그 값)이 있는 포크한 자식 프로세스가 500줄 또는 60 s마다 그 줄들을 `telemetry.jsonl.tmp`에 덧붙입니다. 마지막 걸음은 나머지를 덧붙이고 파일 이름을 `telemetry.jsonl`로 바꾸며 한 줄을 출력합니다. `PYTHON LLM telemetry lines=... appends=... failed_appends=... file=telemetry.jsonl`. 그래서 `telemetry.jsonl`은 마지막 걸음에서만, 완전한 채로 나타납니다. 실행 뒤에 `telemetry.jsonl`이 없거나 `telemetry.jsonl.tmp`가 남아 있으면 텔레메트리가 완료되지 않은 것입니다. `verify_async.py`와 `verify_demo.py`가 둘 다 확인합니다. 콜백은 상태 가운데 첫 상태(SVD 요약의 창 시작)와 마지막 세 상태(그 잔차 추세)만 남깁니다.

2026-10-27까지 콜백은 마지막 걸음까지 모든 상태를 들고 있다가(Python 3.11에서 걸음당 약 1.35 KiB) 파일 전체를 다시 썼고, 마감은 상태마다 1e-4 s였습니다. 요청 워커도 요청 걸음에서 파일을 다시 썼습니다. 끝난 파일의 바이트는 같습니다. `test_callback.TelemetryTests`는 2,345걸음에서 main의 콜백과 비교하고, [10월 28일 점검](../../../docs/evidence/2026-10-28-callback/README.md)은 PODFoam 실행에서, 그리고 10월 27일 주기 실행의 상태 24,000개에서 비교합니다. 거기서 Python 힙은 31.7 MiB까지 느는 대신 최대 0.515 MiB에 머물렀고(tracemalloc의 최댓값. 대기 중인 줄을 최대 한 묶음까지 들고 있으며, 마지막 상태 뒤에는 0.067 MiB가 남았는데 그 상태는 덧붙인 직후에 왔습니다), 마지막 걸음은 0.699 s 대신 0.023 s 걸렸습니다. 비용은 모든 걸음으로 옮겨 갔습니다. CPU 노드의 PODFoam에서 걸음당 콜백 시간 중앙값은 0.079~0.107 ms 대신 0.163~0.217 ms였고(줄 인코딩), 덧붙이는 걸음은 13.7~22.0 ms 걸렸습니다.

자식 프로세스는 성공을 파이프로 알립니다. 쓰지 못했을 수도 있는 줄은 대기 상태로 남고, 다음 자식 프로세스가 한 묶음 뒤에 같은 오프셋에 다시 씁니다. 그래서 끊기거나 실패한 덧붙이기가 끝난 파일에 빈틈이나 잘린 줄을 남기지 않습니다. 대기 중인 줄이 10,000개를 넘으면 콜백은 그 줄을 버리고, `telemetry.jsonl`을 쓰지 않으며, `llm_errors.jsonl`에 한 번 알립니다. 인코딩할 수 없는 상태(앞선 줄은 전처럼 `.tmp`에 남음), 그리고 실패하거나 마감 전에 결과를 알리지 않은 마지막 덧붙이기(main의 마지막 쓰기는 알리지 않았음)에도 똑같이 합니다. 이때 마지막 줄은 `file=telemetry.jsonl.tmp incomplete: <reason>`이고, `.tmp`가 없으면 이유와 함께 `file=none`입니다. 마감에 끊긴 마지막 자식 프로세스는 줄을 출력하지 않으며, `llm_errors.jsonl`의 항목(`PYTHON LLM callback failed open: ...`으로도 출력됨)이 기록입니다. 마지막 걸음 전에 멈춘 실행은 `.tmp`만 남기고 아무것도 알리지 않습니다. 실패하거나 느린 텔레메트리 쓰기는 솔버를 멈추지 않습니다. 그 걸음을 길어야 자식 프로세스의 마감까지 붙잡고, 실패를 알리는 마지막 걸음은 최대 0.2 s 더 붙잡습니다. 마지막 걸음 뒤의 걸음은 `LLM_FINAL_STEP`을 실행 끝보다 앞으로 정했을 때만 생기며, 줄을 받지 않습니다. 전에는 그 뒤의 요청이 그 걸음들을 넣어 파일을 다시 썼습니다. 시험하지 않은 것: 실행 중 실제 디스크 고장이나 가득 찬 디스크.

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

`verify_async.py`는 저장된 모든 시각 폴더가 기준과 같은지, 프레임의 배열이 저장된 필드와 기준의 프레임과 같은지, 요청 걸음이 0.5 s 안에 끝났는지, 요청·도착·마지막 걸음을 뺀 모든 걸음이 1 s 안에 끝났는지, 답(또는 오류)이 도착 걸음과 함께 기록됐는지 확인합니다. sequence 조건에서는 요청 본문의 그림 해시도 확인하고, 2026-10-28부터 v2 실행에서는 `computed_trends`와 `computed_trends_agreement`가 자기 정답과 점수와 같은지, `t`나 `tn` 본문이 빌더의 그 형태인지도 확인합니다. `LLM_LONG_CASES=async-no-llm`은 기준 조건만 돌리므로 모델 요청 없이 프레임을 얻는 방법입니다. 다만 실행기가 첫 조건 전에 서버를 확인하므로 모델을 띄운 llama-server는 있어야 합니다.

## 솔버가 그리는 v2 그림 (`LLM_IMAGE_STYLE=v2`)

`LLM_IMAGE_STYLE=v2`이면 `describe`와 `sequence` 요청이 `state.png` 대신 2026-10-22 그림 읽기 시험의 그림을 보냅니다. 필드마다 1024×576 PNG 한 장(|U|, 그다음 p), 두 축은 그린 범위의 퍼센트이고 10 %마다 격자선이 있으며, 색 막대에는 값 다섯 개를 적습니다(`readable_image.py`). 기본값은 `v1`이고, 이때 솔버는 2026-10-13~2026-10-20의 동작을 바이트까지 그대로 지킵니다. `observe`는 언제나 v1 그림을 보내고, `observe`에 v2를 주면 거부합니다.

- v2 프레임은 모두 `llm_observation/step-NNNNNN/` 폴더 하나이고, 안에 `fields.npz`, `U.png`, `p.png`, 그리고 마지막에 쓰는 `readable-metadata.json`이 있습니다. 요청 걸음의 프레임도 같습니다. 폴더가 이미 있으면(같은 경우 폴더에서 다시 돌린 경우. 걸음 번호는 솔버 프로세스마다 처음부터 다시 셉니다) 덮어쓰지도 보내지도 않고, 그 프레임 저장이나 요청을 거부합니다.
- 요청은 그림 시험과 같은 함수로 `readable_request.py`가 만듭니다. `describe_v2_payload`, 그리고 sequence에는 그림마다 제 색 범위를 쓰는(v2own 프롬프트) `sequence_v2_payload`입니다. v2 sequence는 두세 걸음(그림 최대 여섯 장)을 받습니다. 요청에는 언제나 `max_tokens` 320, 시드 20261021, `cache_prompt: false`가 들어가므로 `LLM_MAX_TOKENS`는 비워 두거나 320이어야 합니다. `test_picture_test.GoldenV2RequestTests`는 발표된 2026-10-22 요청의 바이트를 고정하고, `verify_async.py`는 실시간 본문이 디스크의 프레임에 빌더를 적용한 결과와 바이트까지 같은지 확인합니다.
- v2 describe 요청은 SVD 요약을 보내지 않으므로, 콜백은 스냅샷 창을 쌓지도 계산하지도 않습니다. 그래서 긴 실행의 늦은 걸음에 요청해도 워커가 느려지지 않습니다.
- 계산한 증감 단어(2026-10-28). v2 sequence에서 워커는 증감 단어 세 개도 프레임 배열에서, 그린 범위 안의 칸들로, 그림 시험의 정답 규칙으로 계산합니다(`snapshot_runner.py`: 가장 큰 |U|와 가장 낮은 p는 마지막 값이 첫 값과 두 크기 중 큰 쪽의 2 % 이하로 다르면 거의 그대로이고, 가장 빠른 칸은 그린 범위의 5 % 이하로 움직였으면 같은 자리입니다). `llm_result.json`에 `computed_trends`(`snapshot_runner.sequence_truth`가 그 프레임들에 대해 주는 사전, 시각마다의 극값 포함)로, 모델이 답했으면 `computed_trends_agreement`(그것과 견준 모델의 단어, `snapshot_runner.score_sequence`와 같이)로 기록합니다. 이것은 보내지 않고 `llm_request.json`에도 없으며, 시간이 초과된 요청도 기록합니다. `test_async.ComputedTrendTests`는 시드를 정한 무작위 경우 400개(그린 창 안에 칸이 없으면 다음 뽑기로 바꿈)와 기준값에서 그림 시험의 함수와 견주어 확인합니다.
- `LLM_SEQUENCE_PROMPT`(v2 sequence): `own`(기본)은 2026-10-22 요청을 바이트까지 그대로 보내고, `t`는 정답의 기준을 프롬프트에 적으며, `tn`은 여기에 시각마다 그린 범위 안의 가장 큰 |U|와 가장 낮은 p를 메모에 더합니다. [10월 27일 변화 읽기 시험](../../../docs/results-20261027.md#스냅샷-사이의-변화-읽기)의 `dev-sequence-v2own-t`와 `-tn` 형태이고, 같은 `readable_request.sequence_v2_payload`가 만듭니다. 결과에 `sequence_prompt`를 기록합니다. 다른 값, 그리고 v1 그림에 준 `t`나 `tn`은 프레임을 그리기 전에 거부합니다.
- 그린 범위는 `LLM_IMAGE_XRANGE`/`LLM_IMAGE_YRANGE`, 없으면 전체 영역(3차원 경우는 단면 칸의 영역)입니다. v2에는 칸마다 다각형 하나가 있어야 합니다. x-y 평면의 2차원 경우, 또는 2026-10-28부터 평면 단면을 거친 3차원 경우입니다([솔버 안에서 호출되는 순서](#솔버-안에서-호출되는-순서) 참고). 래스터 대체는 없습니다.
- 서버 컨텍스트는 그림 시험처럼 4096토큰, batch/ubatch 512로 하세요. 세 시각 v2 sequence는 프롬프트가 약 2,200토큰입니다.

`LLM_KILL_JOIN_S`(기본 0.1 s, 2026-10-27 전에는 0.02 s; 최대 2 s)는 끊은 워커를 거두는 데 기다리는 시간입니다. 자식 프로세스가 쓰는 메모리가 클수록 오래 걸립니다. MedicineBow 노드에서는 200 MB에 약 16 ms, 500 MB에 38 ms였고, 0.5 GB 솔버에서 포크한 워커는 0.02 s 안에 거둬지지 않습니다. 그래서 그곳 작업은 0.2 s를 씁니다.

### 발달한 흐름에서 시작하기

`LLM_LONG_START=<시각 폴더>`이면 비동기 시험의 모든 경우가 t = 0 대신, 같은 격자(격자 파일을 해시로 비교)로 돌린 이전 실행의 그 상태에서 시작합니다. 그 필드를 복사하고, 시간 번호가 처음부터 다시 시작하도록 `uniform/`은 빼며, 끝 시각은 시작 시각에 `LLM_LONG_STEPS` × `LLM_LONG_DT`를 더한 값입니다. 콜백의 걸음 번호는 시작부터 셉니다. `LLM_LONG_FIXTURE_DEADLINE_S`(기본 4)는 연결 거부와 멈춤 경우의 콜백 마감입니다. 이런 실행에서 `verify_async.py`는 모든 경우의 시작 파일이 기록된 것과 같은지, Courant 수가 1보다 작은지도 확인합니다.

### 한 연구에서 describe 요청 여러 개 (`run_live_sweep.py`)

비동기 시험은 창 하나에 describe 요청 하나를 보냅니다. 창이 고정이면 답이 늘 비슷한 자리에 있어서, 답 하나로 고정해도 잘 맞습니다. `run_live_sweep.py <시험 실행> <PODFoam> <출력>`은 v2 시험 뒤에 요청 걸음 R마다(기본 500걸음마다) 경우를 하나씩 더 돌립니다. 모두 같은 시작 상태에서 출발하고, R에서의 기준 저장 상태의 가장 빠른 칸 둘레에 무작위로 놓은 창(`window_test.py`의 규칙)으로 R에 describe 요청을 보냅니다. 답이 솔버가 도는 동안 왔는지, 요청 본문이 시험한 빌더를 프레임에 적용한 결과인지, 프레임의 배열이 R에서 기준이 쓴 필드와 같은지 확인하고, 답과, 모든 답에 대해 가장 잘 맞는 고정 답 하나를 채점합니다(`sweep-summary.json`).

### N걸음마다 요청 (`LLM_ANALYSIS_EVERY`)

`LLM_ANALYSIS_EVERY=N`(v2 그림의 describe)이면 `LLM_ANALYSIS_STEP`에서, 그 뒤 N걸음마다 describe 요청을 보냅니다. 대기 중인 요청이 `LLM_ASYNC_MAX_PENDING`보다 적을 때만 보내고, 한도에 걸린 걸음은 건너뛰고 기록합니다. 요청마다 늘 쓰는 파일(`llm_request.json`, `llm_request_body.json`, `llm_response.json`, `llm_result.json`, 원래 답)을 자기 폴더 `llm_requests/step-NNNNNN/`에 쓰고, 마지막 걸음에서 `llm_requests/index.json`(걸음, 상태, 도착 걸음, 모델 시간, 솔버 멈춤, 그리고 2026-10-29부터 `record_written`: 기록 폴더가 0.2 s 한도 안에 써졌는지. 답이 도착한 요청도 이를 놓칠 수 있음)을 씁니다. `run_periodic.py <시험 실행> <PODFoam> <출력>`은 v2 시험의 기준 준비 폴더에서 이런 경우 하나와 요청 없는 쌍둥이를 돌려 저장 파일을 모두 비교하고, 요청 본문을 빌더와, 프레임을 저장 필드와 대조하고, 답을 채점하고, 걸린 시간, 메모리(솔버 프로세스들의 RSS와 PSS, 0.5 s마다), 요청마다 워커 파이프로 오간 바이트(결과의 `ipc_bytes_received`)를 기록합니다. `hpc/periodic_v2.slurm`이 GPU 노드에서 돌립니다.

### 발달한 흐름의 변화 읽기 시험 (`sequence_test.py`)

`sequence_test.py build --states <경우> --centres <fields.npz> --old-manifest ... --output <묶음>`은 저장 상태 세 개씩(기본 간격 2000, 4000, 6000걸음)을 묶고, 묶음마다 가장 빠른 칸들 둘레에 무작위 창 하나를 놓고(위의 창 규칙, 가장 빠른 칸이 모두 여백 안쪽), 정답의 (속력 추세, 압력 추세) 아홉 가지가 상태가 허락하는 만큼 고르게 차도록 `--count`개를 고릅니다. 같은 세 시각 묶음으로 다섯 가지를 만듭니다. `dev-sequence-v1`(솔버의 두 칸 그림, 2026-10-20 프롬프트), `dev-sequence-v2own`(필드 하나씩 그린 그림, 그림마다 자기 색 범위, 2026-10-22 프롬프트), `dev-sequence-v2own-t`(같은 것에 정답의 기준을 프롬프트에 적음: 추세는 2 %, 자리는 그린 범위의 5 %), `dev-sequence-v2own-tn`(여기에 시각마다 배열에서 구한 최대 |U|와 최소 p를 메모에 더함), `dev-sequence-numbers`(그 메모와 가장 빠른 칸의 위치만, 그림 없음). `readable_request.sequence_v2_payload(..., thresholds=True, numbers=..., images=False)`가 만들며, 기본값이면 2026-10-22 본문을 바이트까지 그대로 줍니다. `--dt`(여기와 `window_test.py`)는 상태 이름을 나눌 시간 간격으로, 다른 간격으로 돈 실행에 씁니다. `--y-span`은 창 높이의 범위(m)입니다. 2026-10-27에 돌렸습니다([보고서](../../../docs/results-20261027.md#스냅샷-사이의-변화-읽기)).

### 무작위 창 그림 시험 (`window_test.py`)

`window_test.py build`는 한 실행의 저장 상태(어떤 시각 폴더든; `--first-step`, `--describe-every`, `--last-step`은 5e-7 s 걸음 단위)를 상태마다 여러 번 그리면서, 그린 범위를 가장 빠른 칸 둘레에 무작위로 놓습니다. 그 칸은 모든 가장자리에서 15 % 이상 떨어지고, 안에 칸이 200개 이상 있고, 높이 0.03~0.114 m, 너비는 높이의 1.5~4배입니다. `flow-window-v1`과 `flow-window-v2` 묶음을 쓰고, `check`, `run`, `report`는 `picture_test.py`처럼 동작하며, 고정 답 점수는 묶음 전체에 답 하나로 셉니다. `hpc/window_test.slurm`이 GPU 노드에서 묶음 하나를 돌립니다.

### 불안정 시험 (`instability_test.py`)

`instability_test.py build --design <design.json> --centres <fields.npz> --output <묶음>`은 pimpleFoam 실행을 받습니다. `log.pimpleFoam`과 저장한 시각 폴더가 있는 경우 폴더들이고, 모두 같은 격자입니다. 로그에 `End` 줄이 있는 실행은 끝까지 돈 것입니다. 로그에 부동소수점 예외의 스택 추적(`Foam::sigFpe`)이 있고 `End`가 없는 실행은 로그의 마지막 걸음에서 중단된 것입니다. 그 밖의 로그(아직 도는 실행, 또는 시간 제한이나 손으로, 다른 오류로 멈춘 실행)는 거부합니다. 중단된 실행에서 중단 1~`--within`(기본 10)걸음 전에 끝나는 세 장 묶음은 `unstable`로 이름 붙여 채점합니다. 설계의 `early_steps_to_crash`는 더 앞의 묶음을 더하는데, 답이 얼마나 일찍 바뀌는지 보이려는 것이고 채점하지 않습니다. 끝까지 돈 실행은 실행 전체에 퍼진 `stable` 묶음을 주고, 묶음마다 실행 끝에서 `--margin`(기본 100)걸음 이상 앞에서 끝납니다. 묶음 하나가 `instability-v2own` 요청 하나입니다. 설계의 창(기본은 솔버의 x 0~0.12 m, y 0~0.04 m)에 그린 v2 프레임 세 장(|U|와 p, 저마다 제 색 범위)과, `readable_request.STABILITY_V2OWN_SYSTEM_PROMPT`(수치 불안정의 징후, 예를 들어 이웃한 칸 사이의 진동, 바둑판 무늬, 물리적 원인 없이 커지는 극값), 그리고 `llm_client.py`의 `stability` 답 스키마(`reason`, 최대 300자, 그다음 `stable`, `unstable`, `cannot_tell` 중 하나)입니다. 솔버 콜백은 이 요청을 보내지 않습니다. `LLM_MODE`에 그런 값이 없습니다. `check`와 `run`은 `picture_test.py`처럼 동작합니다. `report`는 균형 점수, 중단까지 남은 걸음별 `unstable` 답, 실행별 답, 고정 답, 그리고 배열에서 구한 기준선 두 개(창 안에서 첫 프레임부터 마지막 프레임까지 최고 |U|의 증가와 이웃한 칸 사이 가장 큰 |U| 차이의 증가)를 냅니다. 서로 다른 정답으로 만든 실행 폴더는 거부합니다. `hpc/window_test.slurm`이 `PICTURE_TEST_SCRIPT=instability_test.py`로 돌립니다. 테스트: `test_instability_test.py`. 2026-10-28에 돌렸습니다([근거 자료](../../../docs/evidence/2026-10-28-instability/README.md)). 모델 네 개는 최고 |U|가 30.8 % 이상 커진 곳에서만, 대부분 필드가 이미 발산한 프레임에서 `unstable`이라 했고, 중단되지 않은 실행에는 한 번도 그렇게 말하지 않았습니다. 최고 |U| 하나만 보는 규칙도 그만큼 맞혔습니다. 그 묶음에는 결함이 있습니다. 요청마다 프레임의 걸음과 시각을 적는데(메모, 캡션, 그림 제목), 중단된 실행의 프레임은 2×10⁻⁵~1.2×10⁻⁴ s 간격이고 끝까지 돈 실행은 2×10⁻⁴~2×10⁻³ s 간격이어서, 적힌 시각만으로 두 부류가 갈립니다. 새 묶음은 두 부류 모두 프레임을 같은 간격으로 두거나 시각을 빼야 합니다.

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
- `LLM_SEQUENCE_PROMPT`: `own`, `t`, `tn`(v2)
- `LLM_ASYNC_MAX_PENDING`: 동시에 진행하는 요청 수, 기본 1(1~8)
- `LLM_ASYNC_END`: 마지막 걸음에서 `wait`(기본) 또는 `detach`
- `LLM_FINAL_STEP`: 마지막 걸음을 직접 지정(기본은 솔버가 넘기는 `end_time_s`로 판단)
- `LLM_IMAGE_XRANGE`, `LLM_IMAGE_YRANGE`: 그릴 창 `"x0,x1"`(m)
- `LLM_SLICE_Z`: 3차원 경우의 평면 단면 z(m), 솔버가 읽음
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
python3 -m unittest test_llm_client test_callback test_ablation_runner test_async test_picture_test test_instability_test -v
```

2026-10-29에 125개(Python 3.11, numpy와 matplotlib 필요; 불안정 시험과 단면 시험을 합치기 전인 2026-10-28에는 108개)이고, `TMPDIR`를 노드의 로컬 디스크에 둔 경우와 NFS에 둔 경우에서 돌렸습니다. `test_callback.TelemetryTests` 중 여섯 개는 2026-10-27의 main 콜백과 비교하며, 그 콜백은 [docs/evidence/2026-10-28-callback/callback-main/python_module.py](../../../docs/evidence/2026-10-28-callback/callback-main/python_module.py)에 보관해 두었습니다. 저장소의 `docs/`가 없는 코드 사본에서는 이 여섯 개를 건너뜁니다.

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
