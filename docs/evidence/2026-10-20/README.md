# 10월 20일 근거

[10월 20일 보고서](../../results-20261020.md)의 원본 기록입니다. 코드 `9449085`
(`23089bb` 이후 솔버·콜백 코드가 바뀜: 비동기 경로, describe·sequence 모드, 그림 창, 상태에 `end_time_s` 추가).

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-20/README.md)

## 폴더

| 폴더 | 내용 |
|---|---|
| [pod-llm-async.pp7agC/](pod-llm-async.pp7agC/) | 3000걸음 실행의 비동기 다섯 조건(전체 영역 그림): 검증, 시간, 설정, 조건별 요청·답·결과·타임라인, 압축한 솔버 로그와 걸음별 기록; 기준·describe·sequence 조건이 그린 프레임(PNG, 배열, 메타데이터); 실행 당시의 콜백 소스 |
| [pod-llm-async.8YC6bG/](pod-llm-async.8YC6bG/) | 그림 창 x = -0.05~0.15 m로 그린 프레임(모델 요청 없음), 250·1250·2750걸음 |
| [replay/describe-full/](replay/describe-full/) | 전체 영역 프레임(250·750·1250걸음)에 describe 요청, 각 3회 |
| [replay/describe-window/](replay/describe-window/) | 창 프레임(250·1250·2750걸음)에 describe 요청, 각 3회 |
| [replay/sequence-full/](replay/sequence-full/) | 전체 영역 프레임 250·750·1250을 한 요청에 담은 sequence 요청 3회 |
| [replay/sequence-window/](replay/sequence-window/) | 창 프레임 250·1250·2750을 담은 sequence 요청 3회 |
| [unit-tests-70.txt](unit-tests-70.txt) | 단위 테스트 70개 출력 |

재생 폴더마다 `manifest.json`(프레임, 순서, 프롬프트 해시), `ground_truth.private.json`
(배열에서 구한 기준 위치와 추세, 모델에는 보내지 않음), 요청별 `*.request.json`, 그리고
요청별 폴더에 보낸 본문, 받은 원문과 파싱한 답, 결과, 채점이 있습니다. `summary.json`이 이를 모읍니다.

## 파일

`log.PODFoam.gz`와 `telemetry.jsonl.gz`는 솔버 로그와 걸음별 기록(3000줄)의 gzip 사본이고,
`timeline.json`은 모델·콜백 관련 줄을 벽시계 시각과 함께 남긴 것입니다. 나머지는 기록 당시 바이트
그대로입니다. [manifest.json](manifest.json)에 모든 파일의 크기와 SHA-256이 있고,
`python3 docs/evidence/check_manifest.py docs/evidence/2026-10-20`으로 검사합니다.

다섯 조건의 모든 시각 폴더를 포함한 전체 솔버 결과는 저장소가 아니라 영문 저장소 릴리스
[pod-insitu-async-2026-10-20](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-async-2026-10-20)에
있습니다(`solver-evidence-pp7agC.tar.gz`, 약 600 MB, `SHA256SUMS.txt`).

일부 기록에 시험 컴퓨터의 경로가 남아 있습니다. 공개된 위치는 이 폴더입니다.
