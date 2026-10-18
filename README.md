# PythonFOAM 한국어판

[영문 저장소](https://github.com/seungminyome/PythonFOAM) · [시험 결과](docs/results.md) · [GitHub 읽는 법](docs/github-guide.ko.md)

내 컴퓨터에서 실행하는 언어 모델이 계산 중인 유체의 상태를 설명할 수 있는지 시험하고 있습니다. 정해진 계산 단계에서 PythonFOAM의 콜백, 즉 계산 도중 호출되는 함수가 수치 요약과 유동 그림을 Gemma에 보냅니다. Gemma는 llama.cpp를 통해 CPU(중앙처리장치, Central Processing Unit)에서 실행됩니다. 답변은 파일에 저장하고, OpenFOAM은 나머지 계산을 이어갑니다. 답변을 계산값이나 설정을 바꾸는 데 사용하지는 않습니다.

시험에서는 모델의 답변을 받은 뒤 계산이 다시 진행됐습니다. 유동을 얼마나 정확하게 설명하는지는 더 확인해야 합니다.

## 이번에 추가한 부분

원본 [PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)은 OpenFOAM과 Python을 연결하는 기능과 PODFoam 예제를 제공합니다. 이 저장소에서는 다음을 추가했습니다.

- 수치 요약과 속도·압력 그림을 로컬 Gemma 4 E2B 모델에 보내는 콜백.
- 답변과 오류 기록을 저장하고, 요청이 실패하거나 제한 시간을 넘겨도 계산을 이어가도록 하는 처리.
- 저장 결과를 비교하는 다섯 가지 시험: 요청 없음, 수치만 전달, 수치와 그림 전달, 연결 거부, 시간 초과.
- 질문과 수치는 같게 두고 그림을 넣거나 뺐을 때의 답변을 비교하는 시험.

## 시험에서 확인한 것

10월 17일에는 연결 실패와 시간 초과를 포함한 다섯 가지 조건 모두 계산을 마쳤습니다. 각 비교 실행에서 저장된 결과 파일은 모델에 요청하지 않은 기준 실행과 바이트 단위로 같았습니다.

한 시점의 유동 자료로 그림 유무를 비교했을 때는 **답변 6개 모두 속력이 가장 큰 위치를 잘못 짚었습니다.** 또한 답변을 기다리는 동안 계산도 멈춥니다. CPU에서 그림을 포함한 호출에 약 78초가 걸렸습니다.

현재 시제품을 실시간 분석에 활용하려면 추가 검증이 필요합니다. 다음에는 더 다양한 유동 상태에서 답변을 확인하고, 모델이 저장된 자료를 분석하는 동안 계산을 계속할 수 있도록 바꿀 계획입니다.

## 더 자세히 보기

먼저 [한국어 실험 보고서](docs/results.md)에서 시험 조건, 측정값과 한계를 확인할 수 있습니다.

- [요청·답변·실행 로그 원본 안내](docs/evidence/2026-10-17/README.md)
- [예제 실행 방법](Solver_Examples/PODFoam/llm_demo/README.md)
- [문서와 전체 실행 자료 내려받기](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18)
- [그림으로 보는 한국어 설명](https://seungminyome.github.io/PythonFOAM-Korean/)

원본 PythonFOAM의 소개와 설치 안내는 [프로젝트 참고 문서](docs/upstream-project.md)에 남겨 두었습니다. 이 연동 작업에도 저장소의 [Argonne 오픈소스 라이선스](LICENSE)가 적용됩니다.

이 저장소는 [영문 PythonFOAM 작업 저장소](https://github.com/seungminyome/PythonFOAM)의 한국어판입니다. 코드와 시험 원본은 같은 자료를 사용하고, 소개와 사용 안내를 한국어로 제공합니다.
