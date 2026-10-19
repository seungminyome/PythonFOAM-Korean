# 변경 기록

날짜는 실행이나 변경이 있었던 날입니다. 기록된 실행에는 그 실행을 만든 코드 버전을 적었습니다.

## 2026-10-19

- 문서 구성 정리: 근거를 날짜별 폴더로, 영문 저장소에는 영문만 두고 한국어는 이 저장소로.
- CI: Python 3.10과 3.12에서 단위 테스트, 근거 파일을 manifest와 대조, 상대 링크 검사, 솔버 코드가 영문 저장소와 같은지 검사.
- `CITATION.cff`, 이 변경 기록, `Makefile`.
- README에 "5단계"의 뜻과 12B 대신 E2B를 쓴 이유를 적음.

## 2026-10-18

- 10월 17일 보고서와 근거 공개. 릴리스 [korean-docs-2026-10-18](https://github.com/seungminyome/PythonFOAM-Korean/releases/tag/korean-docs-2026-10-18).

## 2026-10-17 (코드 `23089bb`)

- 다섯 조건 솔버 실행 `pod-llm-demo.LRfJBN`과 그림 유무 쌍 비교(`ablation_runner.py`). 단위 테스트 56개.
- 콜백 보강: 워커 절대 마감, 결과 파일은 별도 자식 프로세스가 기록, 클라이언트의 요청·응답 크기 제한.

## 2026-10-13 (코드 `9ae54d0`)

- PODFoam 안에서 그림을 보낸 첫 실행 `pod-llm-demo.SwwR2e`. 릴리스 [pod-insitu-demo-2026-10-13](https://github.com/seungminyome/PythonFOAM/releases/tag/pod-insitu-demo-2026-10-13).
- PODFoam의 `analysis_func` 훅, 셀 다각형을 넘기는 `mesh_func`, `pod_image.py`, `bounded_ipc.py`, `llm_client.py`, 다섯 조건 실행기와 검증기.

## 2026-10-10

- OpenFOAM v2106에서 PODFoam 빌드, 연결 검증 `pod-v2106.c5jpOq` 통과(스냅샷·SVD 왕복). 로컬 모델에 수치만 보낸 첫 요청.

## 2026-10-08

- 과제 시작.
