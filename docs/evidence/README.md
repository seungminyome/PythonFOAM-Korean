# 근거 자료

시험 날짜별로 한 폴더씩입니다(`2026-10-19-12b`에는 그날 GPU 노드에서 한 12B 재생이,
`2026-10-22-picture-test`에는 그림 읽기 시험이, `2026-10-22-window-test`에는 그 뒤의 그림 시험이,
`2026-10-22-live-v2`에는 v2 그림으로 한 솔버 실행이 있습니다). 요청, 응답, 배열, 로그는 기록 당시의 바이트를 그대로 두었고(2026-10-20의 솔버 로그와 걸음별 기록은 gzip 사본), 폴더마다 해시 목록이 있습니다.

| 폴더 | 실행 | 코드 | 보고서 |
|---|---|---|---|
| [2026-10-22-live-v2/](2026-10-22-live-v2/README.md) | Slurm 작업 24757460: `pod-llm-async.UM1RyJ`, NVIDIA RTX A6000의 Gemma 4 12B와 v2 그림으로 발달한 흐름에서 시작한 비동기 다섯 조건; 무작위 창 describe 요청 열한 개; 시험 실행(작업 24757458); 검산 스크립트 | `354caf9`(영문 저장소)에 커밋하지 않은 변경(기록함) | [results-20261022-live.md](../results-20261022-live.md) |
| [2026-10-22-window-test/](2026-10-22-window-test/README.md) | Slurm 작업 24757327(Qwen 모델 네 개, 요청 308개), 24757344와 24757382~24757384(무작위 창, 모델 열한 개, 시드 세 개, 이미지 토큰 한도 1024), 24757459(발달한 흐름, 무작위 창); 발달한 흐름 실행(작업 24757429); 정답과 다시 세기 | 그림 시험 묶음(`58e00d9` + `window_test.py`); 작업 24757459는 작업 24757460과 같음 | [results-20261022-live.md](../results-20261022-live.md) |
| [2026-10-22-picture-test/](2026-10-22-picture-test/README.md) | Slurm 작업 24756981: NVIDIA RTX A6000(MedicineBow)에서 미리 만든 같은 요청 308개를 Gemma 4 모델 일곱 개(E2B부터 31B까지)에 하나씩 보냄. 정답과 독립 재채점 포함 | `58e00d9`(영문 저장소), `7435513`(이 저장소) | [results-20261022.md](../results-20261022.md) |
| [2026-10-20/](2026-10-20/README.md) | `pod-llm-async.pp7agC`: 3000걸음의 비동기 다섯 조건; `pod-llm-async.8YC6bG`: 창 프레임; describe·sequence 재생 | `9449085`(영문 저장소), `74553ea`(이 저장소) | [results-20261020.md](../results-20261020.md) |
| [2026-10-19-12b/](2026-10-19-12b/README.md) | Slurm 작업 24696203: NVIDIA A30(MedicineBow)의 Gemma 4 12B QAT로 한 10월 17일 쌍별 재생, 채점된 위치는 없음(그림 답은 "x=0.00 m 근처"라고만 함) | `934da23`(영문 저장소), `f4a99f3`(이 저장소). 요청·채점 코드는 `23089bb`와 같음 | [results.md](../results.md#gpu에서-gemma-4-12b로-같은-재생-2026-10-19) |
| [2026-10-19/](2026-10-19/README.md) | `pod-llm-demo.o5sNLJ`: 10월 17일 실행과 재생의 반복, 해시와 재생 좌표 동일 | `23089bb` (코드), `4187659` (문서, 영문 저장소) | [results.md](../results.md#2026-10-19-반복) |
| [2026-10-17/](2026-10-17/README.md) | `pod-llm-demo.LRfJBN`: 다섯 솔버 조건과 그림 유무 쌍별 비교 | `23089bb` | [results.md](../results.md) |
| [2026-10-13/](2026-10-13/README.md) | `pod-llm-demo.SwwR2e`: 이미지 경로를 넣은 첫 다섯 조건 실행 | `9ae54d0` | [results-20261013.md](../results-20261013.md) |

그림 시험의 압축 파일(모든 요청과 정답이 든 입력 묶음, 작업마다 모든 원본 답이 든 결과)은 영문 저장소의
[picture-test-2026-10-22](https://github.com/seungminyome/PythonFOAM/releases/tag/picture-test-2026-10-22)
릴리스에, v2 솔버 실행의 전체 출력, 시험 실행, 발달한 흐름은
[pod-insitu-v2-2026-10-22](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-v2-2026-10-22)
릴리스에 있습니다.

모든 시각 폴더를 포함한 전체 솔버 결과는 저장소가 아니라 릴리스에 있습니다(2026-10-20은 `pod-llm-async.pp7agC`의 다섯 조건. 창 프레임 실행 `pod-llm-async.8YC6bG`은 릴리스에 없고, 이 저장소에는 시각 폴더 없이 프레임과 실행 기록만 있음): [2026-10-20](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-async-2026-10-20)(영문 저장소), [2026-10-17](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18), [2026-10-13](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-demo-2026-10-13).
