# 변경 기록

날짜는 실행이나 변경이 있었던 날입니다. 기록된 실행에는 그 실행을 만든 코드 버전을 적었습니다.

## 2026-10-20 (코드 `9449085`)

- 비동기 요청(`LLM_ASYNC=1`): 요청 걸음은 워커를 포크하고 바로 복귀. 이후 걸음마다 막힘 없이
  확인해 도착 걸음을 기록하고, 늦은 워커는 종료하며, 대기 요청 수를 제한. 마지막 걸음에서
  남은 요청을 기다리거나 분리.
- 요청 모드: `describe`(그림 한 장, 설명과 가장 빠른 곳·가장 낮은 압력의 위치를 그린 범위의 %로),
  `sequence`(지정 걸음의 프레임을 모아 한 요청으로, 추세 단어).
- `LLM_IMAGE_XRANGE` / `LLM_IMAGE_YRANGE`로 영역 일부만 그림.
- `PythonAnalysis.H`가 `end_time_s`를 넘김.
- `run_async_cases.py`, `verify_async.py`(`POD_SUITE=async`), `snapshot_runner.py`,
  `test_async.py`(14개, 전체 70개).
- 실행: 3000걸음의 비동기 다섯 조건(`pod-llm-async.pp7agC`), 창 프레임(`pod-llm-async.8YC6bG`),
  describe·sequence 재생. 보고서: [docs/results-20261020.md](docs/results-20261020.md).

## 2026-10-19

- `CITATION.cff` 제거: 아직 인용할 논문이 없음. 용어 통일(시간 단계, 그림), 다음 단계에서 12B를 첫 항목으로.
- `test_callback.py`: 그림을 그리는 테스트의 콜백 마감을 4 s로. 공용 CI 러너에서 1 s는 모자랐음. 테스트만 바뀌고 솔버 코드는 그대로.
- 10월 17일 실행과 재생을 반복(`docs/evidence/2026-10-19/`): 해시와 답 동일.
- `llm_demo/hpc/`: GPU 노드에서 Gemma 4 12B로 같은 측정을 되풀이하는 스크립트와 Slurm 작업.
- 문서 구성 정리: 근거를 날짜별 폴더로, 영문 저장소에는 영문만 두고 한국어는 이 저장소로.
- CI: Python 3.10과 3.12에서 단위 테스트, 근거 파일을 manifest와 대조, 상대 링크 검사, 솔버 코드가 영문 저장소와 같은지 검사.
- 이 변경 기록, `Makefile`.
- README에 "5단계"의 뜻과 시험 컴퓨터 사양을 적음.

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
