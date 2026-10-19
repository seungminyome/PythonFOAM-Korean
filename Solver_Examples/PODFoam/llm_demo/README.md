# PODFoam 계산 중 관찰·기록 기능

PODFoam은 선택한 계산 단계에서 속도·압력장의 수치 요약과 그림을 Gemma 4 E2B에 보냅니다. PythonFOAM의 콜백 함수가 전달을 맡고, llama.cpp가 로컬 CPU에서 모델을 실행합니다. 콜백은 정해진 형식의 답변을 저장한 뒤 솔버로 돌아옵니다. 모델의 답변은 U, p, 솔버 설정이나 제어 알고리즘을 바꾸는 데 사용하지 않습니다.

콜백은 동기식입니다. 솔버는 답이 오거나 마감이 될 때까지 기다립니다. 결과는 [10월 17일 보고서](../../../docs/results.md)에 있습니다.

기존 PODFoam 예제에 선택적으로 사용할 수 있는 콜백을 추가했습니다. `snapshot_func`와 `svd_func`만 정의한 기존 모듈도 전과 같이 동작합니다.

## 솔버 안에서 호출되는 순서

시작할 때와 각 단계에서 부르는 함수입니다.

```
PythonCreate.H   startup    mesh_func(centres, volumes, solutionD, rank, cell polygons)   optional, once
PythonComm.H     each step  snapshot_func(U), svd_func(rank) at the SVD interval           as before
PythonAnalysis.H each step  analysis_func(state)                                           optional
```

`state`에는 해당 단계의 시간, 시간 간격 dt, `solverPerformanceDict`에서 가져온 잔차가 들어 있습니다. 잔차 기록은 Ux, Uy, p 각각의 첫 번째·마지막 초기 잔차, 최종 잔차, 선형 방정식 풀이 횟수와 반복 횟수입니다. 계산을 마친 단계의 `phi`로 다시 구한 Courant 수와 연속성 오차, 운동학적 압력의 복사본인 `p_cells`도 전달합니다. 같은 단계의 U는 이미 `snapshot_func`를 통해 전달된 상태입니다.

배열은 모두 복사본입니다. Python이 솔버의 원래 저장 공간을 직접 보지 않습니다. 콜백은 rank 0에서 실행하며, MPI 병렬 실행에서는 비활성화합니다.

콜백 구현은 `llm_demo/python_module.py`에 있습니다. 선택한 한 단계(기본값 5)에서 별도 작업 프로세스를 만들어 다음 작업을 수행합니다.

1. 단계별 측정 기록을 저장하고, 그때까지 모은 스냅샷을 속도 성분별로 나누어 SVD 요약을 계산합니다.
2. `llm_observation/state.png`를 만듭니다. 크기는 640×360이며, 위에는 속력 |U|, 아래에는 p를 표시합니다. 2차원 사례에서는 C++가 `empty` 경계 패치의 면 정보를 넘겨주므로, 값을 보간하지 않고 각 셀을 다각형으로 그립니다. 그림에 사용한 배열은 `fields.npz`에 저장하고, 그 파일의 SHA-256 해시는 PNG 메타데이터에 넣습니다.
3. 요약과 PNG 데이터 URL을 `/v1/chat/completions`로 POST 요청합니다. 응답 형식에는 `observations`, `possible_interpretation`, `checks`라는 문자열 항목 3개가 필요합니다.
4. 요청 기록, 실제 HTTP 요청 본문, 원본 응답과 소요 시간을 저장합니다.

부모 프로세스는 메시지 길이를 표시한 파이프로 결과를 기다립니다. 전체 대기 기한은 `LLM_CALLBACK_DEADLINE_S`로 정하며 기본값은 120초입니다. 기한을 넘기면 작업 프로세스를 종료하도록 처리합니다. 부모가 결과 파일을 직접 쓰지는 않습니다. 별도의 짧게 실행되는 자식 프로세스가 0.2초의 시간 한도 안에서 최종 결과 파일을 씁니다. HTTP 클라이언트는 같은 컴퓨터의 루프백 주소만 허용하고 요청·응답 크기를 제한합니다. 연결, 응답 데이터가 오지 않는 시간, 전체 호출에 각각 시간 제한을 둡니다.

그림 생성에는 matplotlib이 필요합니다. 3차원 대체 방식인 최근접 셀 기반 래스터 그림에는 scipy도 필요합니다. matplotlib은 시작할 때 `mesh_func`에서 한 번 불러오며, 매 계산 단계에서 다시 불러오지 않습니다.

## 실행 방법

OpenFOAM v2106, numpy와 matplotlib이 설치된 Python 3, [C++·Python 연결 검증](../validation/README.md)을 통과한 실행 자료가 필요합니다. 통과한 실행 자료는 기준 사례로 사용합니다. 모델 파일에는 약 3.4 GB의 디스크 공간이, 서버에는 RAM 몇 GB가 필요합니다.

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
- `LLM_MAX_TOKENS`: 최대 192

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
python3 -m unittest test_llm_client test_callback test_ablation_runner -v
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

10월 17일의 [manifest](../../../docs/evidence/2026-10-17/ablation/manifest.json)에 원래 요청과 순서가 있습니다(시드 20261017, 20261018, 20261019, 쌍마다 먼저 보내는 조건을 번갈아 바꿈). 서버 빌드, 가중치, 프로젝터, 스레드 수, 문맥 길이는 실행 사이에 고정하고 `--server-note`로 적어 두세요.

요청마다 본문, 답, 해시, 상태, 측정값을 저장합니다.

- **위치:** x만 답하면 x축 오차를, 두 축을 답하면 그 평면에 투영한 거리를, 세 축을 모두 답하면 3차원 거리를 계산합니다. 좌표가 없거나 뜻이 모호하면 점수를 매기지 않습니다. 요약에는 채점할 수 있었던 답변의 비율도 기록합니다.
- **주장 검사:** 규칙 몇 개가 잘못 인용한 숫자와 근거 없는 단정을 찾습니다. 많이 놓칩니다. 10월 17일 [답 검토](../../../docs/evidence/2026-10-17/independent-ablation-review.json)에 놓친 것이 적혀 있으니 답도 직접 읽으세요.
- **시간:** `replay_callback_wall_s`는 준비된 요청을 보내고, 기다리고, 평가하고, 저장하는 시간을 측정합니다. HTTP 요청과 응답을 기다린 시간도 따로 기록합니다. 이 재생 시험은 솔버, SVD, 그림 생성을 다시 실행하지 않습니다. 같은 실행의 솔버 로그가 있으면 `original_cpp_callback_wall_s`에 당시 콜백 시간을 별도로 기록합니다.

재생은 모델을 시험하는 것이지 솔버 연결을 시험하는 것이 아닙니다. 연결은 다섯 조건 데모와 `verify_demo.py`로 확인하세요.

## 이전 실행 (10월 13일)

`pod-llm-demo.SwwR2e`(솔버 버전 `9ae54d0`)의 측정값과 답변은 [10월 13일 보고서](../../../docs/results-20261013.md)와 [근거 자료](../../../docs/evidence/2026-10-13/README.md)에 있습니다. 당시 그림 요청과 수치만 요청은 지시문이 달라서 그림의 효과를 분리하지 못했습니다. 그 역할은 10월 17일의 재생 비교가 합니다.

## SVD 요약의 의미

두 요청 모두 그때까지 모은 속도 스냅샷의 성분별 SVD 요약을 받습니다. 특이값과 그 비율만 보내고 공간 모드는 보내지 않습니다. `leading_energy_fraction`은 σ₁²를 특이값 제곱의 합으로 나눈 값, 즉 첫 패턴이 스냅샷 행렬에서 차지하는 몫입니다(기록된 실행의 Ux에서 약 99.997%). 행렬은 평균을 빼지 않았고 가중치도 없습니다. 자료 요약일 뿐 물리적 에너지도 정확도 척도도 아니며, 모델에 도움이 되는지는 시험하지 않았습니다.

정상 요청의 작업 프로세스 기한은 120초입니다. 일부러 실패시키는 조건에는 4초 기한과 정리 시간을 포함한 4.27초의 허용 한도를 적용합니다.

[그림을 곁들인 한국어 해설](../../../docs/guide.ko.html) · [영문 원문](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/PODFoam/llm_demo/README.md)
