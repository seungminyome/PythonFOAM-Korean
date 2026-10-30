# 10월 22일 근거: 돌고 있는 솔버가 그린 v2 그림

MedicineBow(와이오밍 대학교)의 Slurm 작업 24757460, NVIDIA RTX A6000 한 장(49,140 MiB), 2026-10-22
09:49\~10:57 MDT. OpenFOAM v2212는 Apptainer 이미지에서 돌렸고, PODFoam은 그 안에서 conda Python 3.11에
맞춰 빌드했습니다. 호스트 GPU에서는 llama.cpp b11429(커밋 `d812350`)가 Gemma 4 12B QAT Q4_0을 띄웠습니다.
코드는 영문 저장소의 `354caf9`에 커밋하지 않은 변경을 얹은 체크아웃입니다([job/code-state/](job/code-state/)).

[보고서](../../results-20261022-live.md) ·
[돌리는 법](../../../Solver_Examples/PODFoam/llm_demo/hpc/README.md#돌고-있는-솔버가-그린-v2-그림-async_v2slurm-2026-10-22-실행) ·
[전체 출력이 있는 릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-v2-2026-10-22) ·
[그림 시험과 발달한 흐름](../2026-10-22-window-test/README.md) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-22-live-v2/README.md)

## 무엇을 돌렸나

- 시작 상태: 같은 격자로 돌린 `pimpleFoam` 실행(작업 24757429)의 t = 0.1 s. 그 `U`, `p`, `phi`의 해시는
  `suite/async-settings.json`에, 그 실행의 설정과 출력은
  [../2026-10-22-window-test/flow/](../2026-10-22-window-test/flow/)에, 저장 상태는 릴리스에 있습니다.
- 다섯 조건(`run_async_cases.py`, `pod-llm-async.UM1RyJ`): 5e-6 s 간격 6000걸음, 250걸음마다 저장, 그림은
  모두 창 x 0\~0.12 m, y 0\~0.04 m. describe, 연결 거부, 멈춤은 250걸음; sequence 프레임은 3000, 3250,
  3750걸음이고 3750걸음에 보냄.
- sweep(`run_live_sweep.py`): 같은 상태에서 경우 열한 개를 더. 500, 1000, …, 5500걸음에 describe 요청
  하나씩, 창은 경우마다 무작위, 300걸음 더 가서 멈춤, 한 번에 두 경우씩.
- 시험 실행(작업 24757458, `pod-llm-async.yIW1TX`, 같은 날 오전 그 전): 600걸음, describe는 100걸음,
  sequence는 200, 300, 500걸음, sweep 요청은 200과 300걸음.

## 파일

| 경로 | 내용 |
|---|---|
| `suite/async-settings.json`, `summary.json`, `async-verification.json`, `timings.json` | 설정; 검증 결과(PASS)와 경우마다의 확인, 답과 점수; 벽시계 시간과 최대 메모리 |
| `suite/build-inputs.json`, `environment.txt`, `log.build`, `resident-server.json`, `sha256.json` | 빌드 입력, 환경, 빌드 로그, 경우들이 쓴 서버, 묶은 실행의 모든 파일 해시(릴리스의 압축 파일) |
| `suite/executed-callback-source/` | 경우들이 실제로 돌린 콜백 소스(`pod_svd.py`는 `validation/python_module.py`) |
| `suite/<경우>/llm_request.json`, `llm_result.json`, `llm_response.json`, `llm_http_response.raw` | 경우마다: 요청 기록(그림 바이트 제외), 결과(상태, 도착 걸음, 솔버 정지, 시간), 해석한 답이 든 기록, HTTP 원문 답 |
| `suite/<경우>/log.PODFoam.gz`, `telemetry.jsonl.gz`, `timeline.json.gz`, `memory-samples.json.gz` | 솔버 로그, 걸음별 기록(6000줄), 벽시계 시각이 붙은 콜백·모델 사건, 메모리 표본(0.5 s마다)의 gzip 사본 |
| `suite/async-describe/llm_request_body.json`, `suite/async-sequence/llm_request_body.json` | 보낸 그대로의 요청 본문 두 개(그림 포함, base64) |
| `suite/async-describe/llm_observation/step-000250/`, `suite/async-sequence/llm_observation/step-003000/`(3250, 3750도) | 프레임: `U.png`, `p.png`, `fields.npz`(칸 중심, U, p), `readable-metadata.json` |
| `suite/async-timeout/timeout-fixture.json` | 멈추는 시험 서버의 기록 |
| `sweep/sweep-plan.json`, `sweep/sweep-summary.json` | 창이 붙은 요청 열한 개; sweep의 확인, 답, 점수 |
| `sweep/describe-stepNNNNNN/` | 경우마다: 요청 기록, 결과, 답, 원문 답, 프레임 |
| `sweep/fields-vs-baseline.json`, `sweep/compare_sweep_fields.py` | 열한 경우가 시작 뒤에 쓴 모든 파일을 기준과 비교: 바이트 비교, 다른 파일은 최댓값 대비 가장 큰 차이 |
| `trial/` | 시험 실행의 설정, 검증, 요약, 시간, describe·sequence 결과, sweep 계획과 요약, 작업 출력 |
| `job/pod-async-v2-24757460.out`, `job/async_v2.slurm` | 작업 출력과 실제로 돌린 작업 스크립트 |
| `job/code-state/` | 작업이 돈 체크아웃에서 기록한 `HEAD`, `git status`, 커밋하지 않은 변경의 패치, 새 파일의 tar 묶음 |
| `job/server/`, `job/nvidia-smi.txt`, `job/gpu-samples.csv.gz`, `job/runtime_manifest_12b.json` | llama-server 명령줄, 로그, 모델 목록, 준비됐을 때 GPU 메모리; 시작 때 GPU와 1초마다의 메모리·부하; 12B 파일 해시 |
| [check-live.py](check-live.py), [check-live.json](check-live.json) | 아래 검산과 그 출력 |
| [courant-spectrum.py](courant-spectrum.py), [courant-spectrum.json](courant-spectrum.json) | 기준 경우의 최대 Courant 수가 오르내리는 주기와 그 출력 |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

## 검산

이 폴더에서, numpy가 있으면:

```bash
python3 check-live.py               # check-live.json을 씀
python3 courant-spectrum.py
python3 ../check_manifest.py .
```

`check-live.py`는 이 폴더의 파일만 씁니다. 실제로 돌린 `readable_request.py`로 프레임마다 요청 본문을 다시
만들어 보낸 본문과 비교합니다. 다섯 조건의 본문 두 개는 바이트로, sweep 본문 열한 개는 클라이언트가 보낸
본문에 대해 기록한 SHA-256으로 비교합니다(13개 중 13개 같음). 프레임 배열에서 가장 빠른 칸과 압력이
가장 낮은 칸, 답의 거리, sequence의 증감 단어, sweep 전체에 대한 가장 좋은 고정 답을 다시 계산하고, 실행의
기록과 같은지 확인합니다. 출력은 보고서의 숫자입니다. 다섯 조건 describe 답은 3.28 %와 5.03 %, sequence는
속도와 위치 맞음·압력 틀림, sweep은 11개 중 9개와 10개가 10 % 안, 고정 답은 4개와 4개입니다.

`compare_sweep_fields.py`는 시각 폴더가 필요하고, 그것은 릴리스에 있습니다.
`solver-evidence-UM1RyJ.tar.gz`와 `sweep-UM1RyJ.tar.gz`를 풀어 두 폴더를 주면 됩니다.

## 참고

- 코드 상태. 체크아웃의 어떤 파일도 09:42 뒤로 바뀌지 않았고 작업은 09:49에 시작했으며, 상태는 10:41에
  기록했습니다. 실행이 기록한 원본 62개(다섯 조건 압축 파일의 `sources/`와 `executed-callback-source/`)가
  모두 체크아웃과 같습니다. 공개한 커밋은 이것과 다르고, 어떻게 다른지는 보고서의
  [기록](../../results-20261022-live.md#기록)에 있습니다.
- describe 본문은 `async-describe`, `async-server-error`, `async-timeout`에서 같은 바이트입니다(같은 프레임,
  같은 요청). 여기에는 `async-describe`의 것만 두었습니다. `async-no-llm`의 프레임(3000, 3250,
  3750걸음)은 `async-sequence`의 것과, `async-server-error`와 `async-timeout`의 프레임(250걸음)은
  `async-describe`의 것과 파일 네 개 모두 바이트까지 같아서 다시 두지 않았습니다.
- 저장 필드. 다섯 조건에서는 경우마다 비교한 파일 432개가 모두 기준과 같습니다. sweep에서는 모든 시각
  폴더의 `U`, `p`, `phi`와 시간 파일이 기준과 같고(파일 858개), PODFoam이 자체 SVD로 쓰는 POD 모드 파일
  (`upod_*`, `vpod_*`, `wpod_*`, 파일 2,145개)은 최댓값 대비 최대 9.4e-12만큼 다릅니다. sweep은 BLAS
  스레드 제한 없이 두 경우씩 돌았고(코드 상태 안의 `run_live_sweep.py`), 차이의 원인은 따로 밝히지
  않았습니다.
- sweep 압축 파일에는 `python_svd_audit.npz`(PODFoam이 실행 끝마다 쓰는 점검 파일, 경우마다 120 MB)와
  matplotlib 캐시가 없습니다. 다섯 조건 압축 파일에는 있습니다.
- gzip 사본(manifest의 종류 `gzip copy`)은 이름 없이, 수정 시각 0으로 만들었고, manifest에 압축 전
  바이트의 해시도 적었습니다.
- 기록에는 출처를 보이려고 클러스터 경로와 프로세스 번호가 남아 있습니다.
