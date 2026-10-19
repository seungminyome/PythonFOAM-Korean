# 2026년 10월 17일 시험 자료

[10월 17일 보고서](../../results.md)의 원본 기록입니다. 솔버 실행 `pod-llm-demo.LRfJBN`, 코드 `23089bbf3447731852fa960d7d25ea18767a3f51`.

[브라우저에서 결과 읽기](https://seungminyome.github.io/PythonFOAM-Korean/results-20261017.html) · [파일 내려받기](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18) · [영어 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-17/README.md)

## 파일

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

[ablation/](ablation/)에는 세 쌍의 재생 요청이 `pair-*` 폴더 하나씩으로 있습니다. 보낸 본문, 받은 원문과 파싱한 답, 결과, 측정값. 솔버 실행이 끝난 뒤 저장된 5단계 상태로 보낸 것입니다.

## 전체 실행

여기에는 읽을 만한 기록만 두었습니다. 릴리스의 `solver-evidence-LRfJBN.tar.gz`에는 다섯 실행의 시각 폴더 전부, pimpleFoam 기준 사례, 검증 코드가 있고, 안의 `README.txt`에 아무것도 다시 실행하지 않고 파일을 검사하는 방법이 있습니다. `SHA256SUMS.txt`는 릴리스 파일의 체크섬입니다. 데모 스크립트가 만드는 작은 `run-archive.tar.gz`는 중간 시각을 빼므로 전체 기록은 릴리스 쪽을 쓰세요.

## 참고

요청, 답, 배열, 로그는 기록 당시 바이트 그대로입니다. `runtime-summary.json`은 실행 환경 기록을 줄인 사본이고 manifest에 변환 자료로 표시했습니다. 일부 기록에 시험 컴퓨터의 경로가 남아 있는데, 공개된 위치는 위 링크입니다.
