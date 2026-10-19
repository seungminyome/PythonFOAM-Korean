# 저장소 읽는 순서

[첫 화면](../README.md) · [시험 보고서](results.md) · [그림으로 보기](https://seungminyome.github.io/PythonFOAM-Korean/)

`PythonFOAM-Korean`은 [영문 저장소](https://github.com/seungminyome/PythonFOAM)와 같은 코드와 시험 기록에 한국어 문서를 붙인 것입니다.

1. [README](../README.md): 무엇을 만들었고 무엇을 쟀는지.
2. [시험 보고서](results.md): 조건, 숫자, 한계.
3. [근거 자료](evidence/2026-10-17/README.md): 요청·답·로그 원문. 직접 대조할 때.
4. [연결 검증](../Solver_Examples/PODFoam/validation/README.md)과 [모델 연동 예제](../Solver_Examples/PODFoam/llm_demo/README.md): 직접 돌려 볼 때.

| 위치 | 내용 |
|---|---|
| `Solver_Examples/PODFoam/` | 시험에 쓴 솔버와 Python 연결 코드 |
| `Solver_Examples/PODFoam/llm_demo/` | 모델 요청, 답 저장, 오류 처리, 비교 시험, 단위 테스트 |
| `Solver_Examples/PODFoam/validation/` | OpenFOAM과 Python 사이 자료 왕복 검증 |
| `docs/results.md` | 10월 17일 보고서 |
| `docs/evidence/` | 날짜별 원본 기록 |
| `docs/*.html` | 브라우저용 그림 설명 |
| 나머지 솔버·난류 모델 예제 | 원본 PythonFOAM 그대로 |

문서의 **코드 버전**은 그 시험에 쓴 소스를 가리킵니다. 그 뒤의 커밋은 문서만
바꾼 것이고 시험을 다시 돌리지 않았습니다. 함수 이름, 명령, JSON 키, 모델의
원문 답, 라이선스는 번역하지 않았습니다.
