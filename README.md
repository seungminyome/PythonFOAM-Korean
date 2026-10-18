# PythonFOAM + Gemma 4 E2B

[English README](https://github.com/seungminyome/PythonFOAM) · [실험 결과](docs/results.md) · [실행 방법](Solver_Examples/PODFoam/llm_demo/README.md)

PODFoam의 5단계 계산 직후 Python 콜백에서 잔차, Courant 수, 연속성 오차와 속도·압력 PNG를 로컬 Gemma 4 E2B Q4_0에 보냅니다. 응답을 기록한 뒤 솔버가 계산을 이어갑니다. 모델 출력은 계산에 반영하지 않습니다.

## 10월 17일 실행 결과

- 모델 미호출, 수치만 전달, 수치+이미지 전달, 연결 거부, 시간 초과의 다섯 실행 모두 10단계를 완료했습니다. 비교한 네 실행의 저장 파일은 각각 **45/45개**가 기준 실행과 바이트 단위로 같았습니다.
- 저장된 한 시점을 수치만/수치+이미지로 세 번씩 물었을 때 **6개 답변 모두 최대 속력 위치를 틀렸습니다.** 그림을 포함한 조건의 위치 오차는 50.97 cm였습니다.
- 이미지 요청의 콜백 시간은 **78.256초**였습니다. 현재는 모델 응답을 기다리는 동안 솔버도 멈춥니다.

계산 중 호출과 기록은 확인했습니다. 다른 유동 조건에서 답변이 얼마나 정확한지는 아직 모릅니다. 수치와 입력 조건은 [실험 보고서](docs/results.md)에 있습니다.

## 작업 기록

| 기간 | 작업 |
|---|---|
| 10/8~10/10 | 과제 시작, PODFoam에서 [수치 입력만 사용한 첫 모델 호출](docs/progress-evidence/2026-10-10-pod-text-verification.json) |
| 10/11~10/13 | 이미지 경로를 PODFoam에 연결하고 [솔버 실행](docs/results-20261013.md) 확인 |
| 10/14~10/16 | 위치 답변 재검사, [그림 유무 비교 입력](docs/progress-evidence/2026-10-16-offline-check.json) 준비 |
| 10/17~10/18 | [솔버·모델 비교 실행](docs/results.md), 자료 공개 |

[상세 기록](docs/progress.ko.md) · [요청·응답·로그](docs/evidence/2026-10-17/README.md) · [전체 실행 자료](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18)

[Argonne PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)의 PODFoam 예제를 확장했습니다. 원본 안내는 [여기](docs/upstream-project.md)에 보관했습니다.
