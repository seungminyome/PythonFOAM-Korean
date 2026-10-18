# PythonFOAM 한국어판

[영문 저장소](https://github.com/seungminyome/PythonFOAM) · [시험 결과](docs/results.md) · [GitHub 읽는 법](docs/github-guide.ko.md)

내 컴퓨터에서 실행하는 언어 모델이 계산 중인 유체의 상태를 설명할 수 있는지 시험하고 있습니다. 정해진 계산 단계에서 PythonFOAM의 콜백, 즉 계산 도중 호출되는 함수가 수치 요약과 유동 그림을 Gemma에 보냅니다. Gemma는 llama.cpp를 통해 CPU(중앙처리장치, Central Processing Unit)에서 실행됩니다. 답변은 파일에 저장하고, OpenFOAM은 나머지 계산을 이어갑니다. 답변을 계산값이나 설정을 바꾸는 데 사용하지는 않습니다.

시험에서는 모델의 답변을 받은 뒤 계산이 다시 진행됐습니다. 유동을 얼마나 정확하게 설명하는지는 더 확인해야 합니다.

## 내가 구현하고 시험한 것

원본 [PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)은 OpenFOAM과 Python을 연결하는 기능과 PODFoam 예제를 제공합니다. 내가 만든 코드와 검증한 내용은 다음과 같습니다.

- 수치 요약과 속도·압력 그림을 로컬 Gemma 4 E2B 모델에 보내는 콜백.
- 답변과 오류 기록을 저장하고, 요청이 실패하거나 제한 시간을 넘겨도 계산을 이어가도록 하는 처리.
- 저장 결과를 비교하는 다섯 가지 시험: 요청 없음, 수치만 전달, 수치와 그림 전달, 연결 거부, 시간 초과.
- 질문과 수치는 같게 두고 그림을 넣거나 뺐을 때의 답변을 비교하는 시험.

## 시험에서 확인한 것

10월 17일에는 AI를 부르지 않은 실행을 기준으로 네 번 더 계산했습니다. 수치만 보냈을 때, 수치와 그림을 보냈을 때, AI 서버가 연결을 거부했을 때, 응답을 일부러 늦춰 4초 제한에 걸렸을 때입니다. 다섯 실행 모두 10단계를 마쳤고, 기준 외 네 실행의 저장 파일은 각각 45개씩 기준 실행과 바이트 단위로 같았습니다.

한 시점의 유동 자료로 그림 유무를 비교했을 때는 **답변 6개 모두 속력이 가장 큰 위치를 잘못 짚었습니다.** 또한 답변을 기다리는 동안 계산도 멈춥니다. CPU에서 그림을 포함한 호출에 약 78초가 걸렸습니다.

현재 시제품을 실시간 분석에 활용하려면 추가 검증이 필요합니다. 다음에는 더 다양한 유동 상태에서 답변을 확인하고, 모델이 저장된 자료를 분석하는 동안 계산을 계속할 수 있도록 바꿀 계획입니다.

## 날짜별 진행 기록

아래는 첫 연결부터 한국어판 공개까지, 날짜가 확인되는 작업을 순서대로 적은 것입니다. 교수님께 발표한 날짜를 뜻하지는 않습니다. [각 날짜의 근거와 범위](docs/progress.ko.md)도 볼 수 있습니다.

| 날짜 | 한 일 |
|---|---|
| 10월 13일 | [OpenFOAM v2106과 Python의 연결을 확인](https://github.com/seungminyome/PythonFOAM-Korean/commit/e9b3598)하고, 계산 중 수치·그림을 Gemma에 보내 답을 저장하는 [첫 예제](https://github.com/seungminyome/PythonFOAM-Korean/commit/f053736)를 만들었습니다. |
| 10월 14일 | 13일 결과를 쉽게 설명하는 [그림 해설 초안](https://seungminyome.github.io/PythonFOAM-Korean/progress-evidence/2026-10-14-overview-draft.html)을 작성하고 1차 확인했습니다. |
| 10월 15일 | 저장된 계산값과 AI의 위치 답변을 다시 확인하고, [실행 기록과 설명 자료](https://github.com/seungminyome/PythonFOAM-Korean/commit/034577e)를 정리했습니다. |
| 10월 16일 | 숫자만 보내는 경우와 그림도 보내는 경우의 요청 6개를 준비하고 [오프라인 검사](docs/progress-evidence/2026-10-16-offline-check.json)를 했습니다. 이때 모델에 다시 요청하지는 않았습니다. |
| 10월 17일 | 요청 실패 처리와 비교 실행기를 완성한 뒤 [솔버 다섯 실행과 그림 유무 비교](docs/results.md)를 시험했습니다. |
| 10월 18일 | 시험 결과의 표현을 다듬고 [한국어 저장소와 자료 묶음](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18)을 공개했습니다. |

## 더 자세히 보기

먼저 [한국어 실험 보고서](docs/results.md)에서 시험 조건, 측정값과 한계를 확인할 수 있습니다.

- [요청·답변·실행 로그 원본 안내](docs/evidence/2026-10-17/README.md)
- [예제 실행 방법](Solver_Examples/PODFoam/llm_demo/README.md)
- [문서와 전체 실행 자료 내려받기](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18)
- [그림으로 보는 한국어 설명](https://seungminyome.github.io/PythonFOAM-Korean/)

원본 PythonFOAM의 소개와 설치 안내는 [프로젝트 참고 문서](docs/upstream-project.md)에 남겨 두었습니다. 이 연동 작업에도 저장소의 [Argonne 오픈소스 라이선스](LICENSE)가 적용됩니다.

이 저장소는 [영문 PythonFOAM 작업 저장소](https://github.com/seungminyome/PythonFOAM)의 한국어판입니다. 코드와 시험 원본은 같은 자료를 사용하고, 소개와 사용 안내를 한국어로 제공합니다.
