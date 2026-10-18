# 2026년 10월 17일 시험 자료

이 폴더는 [10월 17일 보고서](../../results.md)의 근거 자료를 담고 있습니다. 솔버 실행 이름은 `pod-llm-demo.LRfJBN`이며, 사용한 코드 버전은 `23089bbf3447731852fa960d7d25ea18767a3f51`입니다.

[브라우저에서 결과 읽기](https://seungminyome.github.io/PythonFOAM-Korean/results-20261017.html) · [파일 내려받기](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18) · [영어 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-17/README.md)

## 필요한 기록 찾기

| 파일 | 담긴 내용 |
|---|---|
| [test-results.json](test-results.json) | 솔버 시험과 통제 비교 결과 요약 |
| [independent-integration-check.json](independent-integration-check.json) | 소스 확인, 비교한 파일 45개, 솔버가 진행한 순서 |
| [runtime-summary.json](runtime-summary.json) | 모델·프로젝터 해시와 서버 설정 |
| [unit-tests-56.txt](unit-tests-56.txt) | Python 및 로컬 HTTP 테스트 56개의 실행 출력 |
| [manifest.json](manifest.json) | 파일 출처, 크기, 해시와 원본·변환 자료 구분 |
| [솔버 검증 결과](pod-llm-demo.LRfJBN/demo-verification.json) | 다섯 솔버 조건을 검사한 결과 |
| [이미지 요청](pod-llm-demo.LRfJBN/fixed-pod/llm_request_body.json) | 계산 중 보낸 요청 본문과 PNG |
| [이미지 응답](pod-llm-demo.LRfJBN/fixed-pod/llm_response.json) | 해당 솔버 실행 중 받은 모델 답변 |
| [state.png](pod-llm-demo.LRfJBN/fixed-pod/llm_observation/state.png) | 5단계에서 보낸 그림 |
| [fields.npz](pod-llm-demo.LRfJBN/fixed-pod/llm_observation/fields.npz) | 그림의 바탕이 된 셀 좌표, 속도, 압력 |
| [재생 비교 설정](ablation/manifest.json) | 공통 질문, 설정, 시드, 요청 해시와 실행 순서 |
| [재생 비교 요약](ablation/summary.json) | 자동 평가기가 계산한 점수 |
| [답변 검수](independent-ablation-review.json) | 답변을 별도로 검토하고 자동 검사가 놓친 주장을 정리한 기록 |
| [기준 좌표](ablation/ground_truth.private.json) | 채점에 사용한 최대속도 위치. 모델에는 전달하지 않았습니다. |

[ablation](ablation/) 폴더에는 저장된 상태를 사용한 세 쌍의 비교가 있습니다. 각 `pair-*` 폴더에는 요청, 응답 원문, 파싱한 응답, 처리 결과와 측정값이 들어 있습니다. 솔버가 계산하는 도중 보낸 요청과는 별도의 시험입니다. 점수와 시간의 의미는 보고서의 [해석 범위와 한계](../../results.md#한계)를 참고하세요.

## 전체 실행 자료 내려받기

이 폴더에는 주요 기록을 선별해 두었습니다. 릴리스의 `solver-evidence-LRfJBN.tar.gz`에는 다섯 조건 각각의 10개 저장 시각 폴더, 기준이 되는 pimpleFoam 사례, 검증 코드까지 들어 있습니다. 압축을 풀면 `README.txt`에서 솔버나 모델을 다시 실행하지 않고 저장 파일을 검사하는 방법을 볼 수 있습니다.

근거 자료 ZIP에는 한국어 결과 페이지와 연결된 파일이 함께 들어 있어 오프라인에서도 읽을 수 있습니다. `SHA256SUMS.txt`에는 두 압축 파일의 체크섬이 있습니다. 자동으로 생성된 이전 `run-archive.tar.gz`에는 중간 시각 일부가 빠져 있으므로, 전체 솔버 기록은 `solver-evidence-LRfJBN.tar.gz`를 사용하세요.

## 저장된 파일에 관하여

요청, 응답, 배열, 로그는 기록 당시의 바이트를 유지했습니다. `runtime-summary.json`은 실행 환경 정보를 줄여 정리한 자료이며, 목록 파일에도 변환 자료로 표시했습니다.

원본 기록에 남아 있는 로컬 경로 대신 위의 상대 링크를 사용하면 공개된 파일을 열 수 있습니다. `remote_writes` 항목은 자료를 게시하기 전의 시험 세션을 설명합니다.
