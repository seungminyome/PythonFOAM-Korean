# PythonFOAM 작업 기록 · 2026년 10월 8~18일

[프로젝트 소개](../README.md) · [교수님 제안과의 대조](professor-alignment.ko.md) · [10월 17일 시험 결과](results.md)

교수님 제안을 받은 날부터 작업을 적었습니다. **10월 8일은 제안일이며 구현일이 아닙니다.** 9일의 복제와 12일의 초안은 로컬 Git 작업 기록으로 확인했습니다. 10·11일의 로컬 시험 자료는 당시 보관한 검증 파일을 아래에 붙였습니다. 12일의 초안 커밋은 다음날 코드 정리 과정에서 교체되어 현재 공개 브랜치에는 없습니다. 13일 이후는 공개 커밋과 실험 자료로 확인할 수 있습니다. 14일과 16일에는 GitHub 커밋이 없지만 당시 만든 파일이 남아 있습니다.

| 날짜 | 확인할 수 있는 작업 | 근거 |
|---|---|---|
| **10월 8일** | 교수님이 PythonFOAM에 공개된 경량 멀티모달 언어 모델을 연결해, 계산 중인 OpenFOAM 상태를 읽고 사용자를 위한 분석을 해보자고 제안했습니다. 특정 12B 모델은 예시였습니다. 이 날 작업을 완료했다는 뜻은 아닙니다. | 사용자가 제공한 10월 8일 이메일; [교수님이 예시로 보낸 모델](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-unquantized) |
| **10월 9일** | 원본 PythonFOAM 저장소를 로컬에 복제했습니다. 이 날의 구현이나 실행 자료는 확인하지 못했습니다. | 로컬 Git reflog의 `2026-10-09 16:07:05 -06:00` 복제 기록; [원본 저장소](https://github.com/argonne-lcf/PythonFOAM) |
| **10월 10일** | PODFoam에서 계산 중 수치 요약을 로컬 Gemma에 보내고 답을 받은 뒤 10단계를 마친 기록이 있습니다. 모델 입력은 텍스트뿐이었습니다. 기준·모델·연결 오류·시간 초과의 네 실행을 기록했고, 저장 파일 45개가 일치했습니다. 이미지 전달의 근거는 아닙니다. | [당시 PODFoam 검증 파일](progress-evidence/2026-10-10-pod-text-verification.json), 로컬 요청 기록의 `2026-10-11T04:35:14Z` 시작 시각(현지 10월 10일 22:35) |
| **10월 11일** | 별도 고체 솔버 확장에서 수치와 이미지 한 장을 모델에 보내고 다음 계산 단계로 넘어가는 시험을 했습니다. 두 단계, 저장 필드 여섯 개만 비교했습니다. 이 결과는 PythonFOAM 저장소의 PODFoam 이미지 연결 시험으로 셀 수 없습니다. | [당시 별도 고체 예제 검증 파일](progress-evidence/2026-10-11-solid-image-verification.json) |
| **10월 12일** | 교수님 제안과 고체·SVD 쪽 작업의 범위를 다시 점검하고, PODFoam 안에 수치와 이미지를 보내는 코드를 초안으로 작성했습니다. 초안 커밋은 13일 정리 과정에서 교체됐습니다. 이날 PODFoam의 실제 이미지 요청 성공을 주장하지 않습니다. | 로컬 Git reflog의 `2c63402`, `73115f5`, `134bdfc` 커밋(20:29 -06:00); 10월 12일 로컬 방향 점검 메모 |
| **10월 13일** | OpenFOAM v2106의 PODFoam과 Python 연결을 공개 코드로 정리하고, 솔버 안에서 수치·이미지를 Gemma에 보낸 뒤 계산이 10단계까지 이어지는 실행을 확인했습니다. | [연결 코드](https://github.com/seungminyome/PythonFOAM-Korean/commit/e9b3598), [모델 연결 코드](https://github.com/seungminyome/PythonFOAM-Korean/commit/f053736), [당시 실행 보고서](results-20261013.md) |
| **10월 14일** | 첫 실행을 쉽게 설명하는 그림 해설 초안을 작성하고 1차 확인했습니다. 이 파일은 당시 설명 초안이므로 최신 실험 결과는 17일 보고서를 보세요. | [당시 초안](https://seungminyome.github.io/PythonFOAM-Korean/progress-evidence/2026-10-14-overview-draft.html), [초안의 내용 확인값](progress-evidence/2026-10-14-overview-sha256.json) |
| **10월 15일** | 13일에 저장한 자료에서 최대 속력의 실제 위치와 AI 답변의 차이를 다시 계산하고, 결과·그림·원본 기록을 정리했습니다. 이 재검사는 유체 계산이나 모델을 다시 돌린 실험이 아닙니다. | [수치 재검사](evidence/numeric_audit_20261015.json), [자료 정리 커밋](https://github.com/seungminyome/PythonFOAM-Korean/commit/034577e) |
| **10월 16일** | 수치만 / 수치+그림 조건의 요청 6개를 로컬에서 준비하고 입력 차이가 그림뿐인지 검사했습니다. Python·로컬 통신 시험 56개를 통과했지만, 이 날은 실제 모델 요청이나 새 솔버 실행을 하지 않았습니다. | [오프라인 준비 검사](progress-evidence/2026-10-16-offline-check.json) |
| **10월 17일** | 요청 실패와 시간 초과 뒤 계산이 이어지는지 시험했습니다. 다섯 솔버 실행은 각각 10단계를 끝냈고, 네 비교 실행의 저장 파일은 각각 45개씩 기준과 같았습니다. 저장한 한 시점으로 그림 유무를 비교한 답변 6개는 최대 속력의 위치를 모두 틀렸습니다. | [코드와 시험 준비](https://github.com/seungminyome/PythonFOAM-Korean/commit/23089bb), [시험 보고서](results.md), [원본 기록](evidence/2026-10-17/README.md) |
| **10월 18일** | 결과를 처음 읽는 사람이 이해할 수 있게 소개와 보고서 문장을 정리하고 한국어판을 별도 저장소로 공개했습니다. 실험을 새로 실행한 날로 적지 않습니다. | [한국어 공개 자료](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18), [변경 기록](https://github.com/seungminyome/PythonFOAM-Korean/commits/main/) |

10월 13일의 약 25 cm 오차는 x축만 계산한 값입니다. 17일의 60.92 cm와 50.97 cm는 x-y 평면 거리라 같은 척도로 성능이 좋아졌는지 비교할 수 없습니다. 날짜별 기록은 진행 과정을 보여주고, 결과의 의미와 한계는 [시험 보고서](results.md)에서 확인할 수 있습니다.
