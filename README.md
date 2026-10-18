# PythonFOAM 한국어판

[영문 저장소](https://github.com/seungminyome/PythonFOAM) · [시험 결과](docs/results.md) · [GitHub 읽는 법](docs/github-guide.ko.md)

10월 8일 교수님이 PythonFOAM에 공개된 경량 멀티모달 모델을 연결해 보자고 제안했습니다. OpenFOAM이 계산하는 동안 나온 숫자와 그림을 모델이 읽고, 사용자에게 쓸 만한 설명을 남길 수 있을지 보는 일입니다.

나는 기존 PODFoam 예제의 Python 콜백에 로컬 Gemma 4 E2B 모델을 연결했습니다. 5단계 계산이 끝나면 수치 요약과 속도·압력 그림을 보내고, 받은 답을 파일에 적은 뒤 계산을 이어갑니다. 모델은 llama.cpp를 통해 CPU에서 실행합니다. 지금 코드는 답변을 계산에 반영하지 않습니다.

## 내가 구현하고 시험한 것

원본 [PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)은 OpenFOAM과 Python을 연결하는 기능과 PODFoam 예제를 제공합니다. 내가 만든 코드와 검증한 내용은 다음과 같습니다.

- 수치 요약과 속도·압력 그림을 로컬 Gemma 4 E2B 모델에 보내는 콜백.
- 답변과 오류 기록을 저장하고, 요청이 실패하거나 제한 시간을 넘겨도 계산을 이어가도록 하는 처리.
- 저장 결과를 비교하는 다섯 가지 시험: 요청 없음, 수치만 전달, 수치와 그림 전달, 연결 거부, 시간 초과.
- 질문과 수치는 같게 두고 그림을 넣거나 뺐을 때의 답변을 비교하는 시험.

## 시험에서 확인한 것

10월 17일에는 AI를 부르지 않은 실행을 기준으로 네 번 더 계산했습니다. 수치만 보냈을 때, 수치와 그림을 보냈을 때, AI 서버가 연결을 거부했을 때, 응답을 일부러 늦춰 4초 제한에 걸렸을 때입니다. 다섯 실행 모두 10단계를 마쳤고, 기준 외 네 실행의 저장 파일은 각각 45개씩 기준 실행과 바이트 단위로 같았습니다.

한 시점의 유동 자료로 그림 유무를 비교했을 때는 **답변 6개 모두 속력이 가장 큰 위치를 잘못 짚었습니다.** 또한 답변을 기다리는 동안 계산도 멈춥니다. CPU에서 그림을 포함한 호출에 약 78초가 걸렸습니다.

그래서 지금 보여줄 수 있는 성과는 **계산 중 모델 연결과 기록**입니다. 답변이 실제로 도움이 되는지는 다른 유동 상태에서도 확인해야 합니다. 모델을 기다리는 동안 솔버가 계속 돌게 하는 것도 다음 작업입니다. [교수님 제안과 지금 결과를 대조한 글](docs/professor-alignment.ko.md)에 판단 근거를 적었습니다.

## 진행 과정 (2026년 10월)

날짜를 하루씩 채우기보다 작업이 바뀐 구간으로 묶었습니다. [자세한 작업 기록](docs/progress.ko.md)에 당시 파일과 실행 결과를 연결해 두었습니다.

| 기간 | 한 일 |
|---|---|
| 10/8~10/10 | 제안을 받고 PythonFOAM을 살펴본 뒤, PODFoam에서 [수치만 보내는 첫 모델 호출](docs/progress-evidence/2026-10-10-pod-text-verification.json)을 돌렸습니다. |
| 10/11~10/13 | 별도 고체 예제에서 그림 전달을 시험하고 이를 PODFoam에 옮겼습니다. 13일에는 [솔버 안에서 이미지 요청 후 계산이 이어지는 실행](docs/results-20261013.md)을 확인했습니다. |
| 10/14~10/16 | 첫 답변의 위치를 원본 계산값과 대조하고, [그림 유무를 비교할 요청](docs/progress-evidence/2026-10-16-offline-check.json)을 준비했습니다. |
| 10/17~10/18 | [실패 상황을 포함한 솔버 실행과 답변 비교](docs/results.md)를 마친 뒤, 결과와 한계를 한국어로 정리해 공개했습니다. |

## 더 자세히 보기

먼저 [한국어 실험 보고서](docs/results.md)에서 시험 조건, 측정값과 한계를 확인할 수 있습니다.

- [요청·답변·실행 로그 원본 안내](docs/evidence/2026-10-17/README.md)
- [예제 실행 방법](Solver_Examples/PODFoam/llm_demo/README.md)
- [문서와 전체 실행 자료 내려받기](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18)
- [그림으로 보는 한국어 설명](https://seungminyome.github.io/PythonFOAM-Korean/)

원본 PythonFOAM의 소개와 설치 안내는 [프로젝트 참고 문서](docs/upstream-project.md)에 남겨 두었습니다. 이 연동 작업에도 저장소의 [Argonne 오픈소스 라이선스](LICENSE)가 적용됩니다.

이 저장소는 [영문 PythonFOAM 작업 저장소](https://github.com/seungminyome/PythonFOAM)의 한국어판입니다. 코드와 시험 원본은 같은 자료를 사용하고, 소개와 사용 안내를 한국어로 제공합니다.
