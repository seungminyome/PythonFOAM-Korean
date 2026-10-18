# PythonFOAM 작업 기록 · 2026년 10월 13~18일

[프로젝트 소개](../README.md) · [10월 17일 시험 결과](results.md)

개발과 확인 작업을 날짜별로 적었습니다. 실험 자료와 실제 Git 커밋을 기준으로 썼습니다. 14일과 16일에는 GitHub 커밋이 없지만, 그때 만든 파일을 보관해 두었습니다.

| 날짜 | 확인할 수 있는 작업 | 근거 |
|---|---|---|
| **10월 13일** | OpenFOAM v2106의 PODFoam과 Python 연결을 검증하고, 로컬 Gemma에 수치·이미지를 보내 답을 저장하는 예제를 만들었습니다. 5단계에서 요청한 뒤 계산이 10단계까지 진행한 첫 실행도 기록했습니다. | [연결 코드](https://github.com/seungminyome/PythonFOAM-Korean/commit/e9b3598), [모델 연결 코드](https://github.com/seungminyome/PythonFOAM-Korean/commit/f053736), [당시 실행 보고서](results-20261013.md) |
| **10월 14일** | 첫 실행을 쉽게 설명하는 그림 해설 초안을 작성하고 1차 확인했습니다. 이 파일은 당시 설명 초안이므로 최신 실험 결과는 17일 보고서를 보세요. | [당시 초안](https://seungminyome.github.io/PythonFOAM-Korean/progress-evidence/2026-10-14-overview-draft.html), [초안의 내용 확인값](progress-evidence/2026-10-14-overview-sha256.json) |
| **10월 15일** | 13일에 저장한 자료에서 최대 속력의 실제 위치와 AI 답변의 차이를 다시 계산하고, 결과·그림·원본 기록을 정리했습니다. 이 재검사는 유체 계산이나 모델을 다시 돌린 실험이 아닙니다. | [수치 재검사](evidence/numeric_audit_20261015.json), [자료 정리 커밋](https://github.com/seungminyome/PythonFOAM-Korean/commit/034577e) |
| **10월 16일** | 수치만 / 수치+그림 조건의 요청 6개를 로컬에서 준비하고 입력 차이가 그림뿐인지 검사했습니다. Python·로컬 통신 시험 56개를 통과했지만, 이 날은 실제 모델 요청이나 새 솔버 실행을 하지 않았습니다. | [오프라인 준비 검사](progress-evidence/2026-10-16-offline-check.json) |
| **10월 17일** | 요청 실패와 시간 초과 뒤 계산이 이어지는지 시험했습니다. 다섯 솔버 실행은 각각 10단계를 끝냈고, 네 비교 실행의 저장 파일은 각각 45개씩 기준과 같았습니다. 저장한 한 시점으로 그림 유무를 비교한 답변 6개는 최대 속력의 위치를 모두 틀렸습니다. | [코드와 시험 준비](https://github.com/seungminyome/PythonFOAM-Korean/commit/23089bb), [시험 보고서](results.md), [원본 기록](evidence/2026-10-17/README.md) |
| **10월 18일** | 결과를 처음 읽는 사람이 이해할 수 있게 소개와 보고서 문장을 정리하고 한국어판을 별도 저장소로 공개했습니다. 실험을 새로 실행한 날로 적지 않습니다. | [한국어 공개 자료](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18), [변경 기록](https://github.com/seungminyome/PythonFOAM-Korean/commits/main/) |

10월 13일의 약 25 cm 오차는 x축만 계산한 값입니다. 17일의 60.92 cm와 50.97 cm는 x-y 평면 거리라 같은 척도로 성능이 좋아졌는지 비교할 수 없습니다. 날짜별 기록은 진행 과정을 보여주고, 결과의 의미와 한계는 [시험 보고서](results.md)에서 확인할 수 있습니다.
