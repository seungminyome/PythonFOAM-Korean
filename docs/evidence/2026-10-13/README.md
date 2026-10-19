# 2026년 10월 13일 실행 자료 · `pod-llm-demo.SwwR2e`

코드 `9ae54d0`, 실행일 2026-10-13. 10월 15일의 재확인 파일은 저장된 자료만 다시 읽은 것입니다. 고친 코드로 다시 돌린 실행과 쌍 비교는 [2026-10-17](../2026-10-17/README.md)에 있습니다.

[10월 13일 보고서](../../results-20261013.md) · [문서 안에서 원본 보기](https://seungminyome.github.io/PythonFOAM-Korean/guide.ko.html#raw-library) · [전체 실행 기록 내려받기](https://github.com/seungminyome/PythonFOAM/releases/download/pod-insitu-demo-2026-10-13/run-archive-SwwR2e.tar.gz) · [영어 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-13/README.md)

| 파일 | 담긴 내용 |
|---|---|
| [summary.json](summary.json) | 다섯 시험의 결과와 AI 답변 |
| [image_request_record.json](image_request_record.json) | `input`에 담긴 잔차·Courant 수·SVD 요약·그림의 수치 정보 |
| [image_request_body.json](image_request_body.json) | 문자로 인코딩한 그림까지 포함한 요청 본문 전체 |
| [image_response.json](image_response.json) | 그림을 보냈을 때의 응답. `api_response → choices → message → content`에서 AI 답변을 확인할 수 있습니다. |
| [image_http_body.raw](image_http_body.raw) | HTTP 머리말을 제외하고 받은 응답 본문 |
| [text_request_body.json](text_request_body.json) | 수치만 보낸 요청. 그림을 보낸 조건과 지시문·추가 정보도 달랐음을 확인할 수 있습니다. |
| [text_response.json](text_response.json) | 잔차·Courant 수·SVD 요약에 대한 AI 답변 |
| [demo-verification.json](demo-verification.json) | 계산 단계 수, 파일 45개 일치 여부, 소요 시간 검사 |
| [verification_recheck_20261015.json](verification_recheck_20261015.json) | 새 계산이나 AI 실행 없이 저장된 기록을 재검사한 결과 |
| [numeric_audit_20261015.json](numeric_audit_20261015.json) | 저장된 수치로 다시 구한 최대속도 위치와 첫 다섯 시점의 SVD |
| [image_run_log.txt](image_run_log.txt) | 5단계 → AI 응답 → 6단계 → `End` 순서를 확인할 수 있는 솔버 로그 |
| [telemetry.jsonl](telemetry.jsonl) | 한 줄에 한 단계의 상태를 담은 JSONL 기록 |
| [timings.json](timings.json) | 전체 실행 시간. AI 호출 시간과 구분해서 읽어야 합니다. |
| [resident-server.json](resident-server.json) | 모델 이름, CPU 설정, 이미지 프로젝터를 불러온 기록 |
| [build-inputs.json](build-inputs.json) | 사용한 OpenFOAM 버전, 실행 파일과 소스 코드 정보 |
| [source_HEAD.txt](source_HEAD.txt) | 실행에 사용한 Git 코드 버전 |
| [image-metadata.json](image-metadata.json) | 그림의 계산 단계, 표시한 값, 원본 파일 정보 |
| [state.png](state.png) | 요청 본문에 포함된 그림과 내용이 같은 PNG 원본 |
| [fields.npz](fields.npz) | 20,540개 셀의 위치, 세 방향 속도, 압력을 담은 NumPy 배열 |
| [python_svd_audit.npz](python_svd_audit.npz) | 저장된 속도 스냅샷. 첫 5시점을 사용해 AI에 보낸 SVD 요약을 다시 계산할 수 있습니다. |
| [python_module.py](python_module.py) | 실행 당시 보관한 Python 콜백 코드 |
| [pod_svd.py](pod_svd.py) | 실행 당시 보관한 SVD 계산 코드 |
| [pod_image.py](pod_image.py) | 실행 당시 보관한 그림 생성 코드 |
| [llm_client.py](llm_client.py) | 실행 당시 보관한 AI 서버 통신 코드 |
| [bounded_ipc.py](bounded_ipc.py) | 실행 당시 보관한 프로세스 간 통신 코드 |
| [errorresult.json](errorresult.json) | 연결 실패를 기록하고 계산으로 돌아온 결과 |
| [timeoutresult.json](timeoutresult.json) | 응답 대기 시간을 넘긴 뒤 계산으로 돌아온 결과 |
| [derived_cells_step5.csv](derived_cells_step5.csv) | 수치 원본을 표 형태로 변환한 CSV |
| [verify_demo.py](verify_demo.py) | 저장된 파일을 대조하는 검사 코드. AI를 새로 호출하지 않습니다. |

[manifest.json](manifest.json)에는 원래 경로, 파일 크기, SHA-256 해시가 있습니다. 재검사 또는 변환 자료로 표시된 파일을 제외하면, 저장 당시의 바이트를 그대로 복사한 자료입니다.

`derived_cells_step5.csv`는 `fields.npz`에서 내보낸 표입니다. `numeric_audit_20261015.json`에는 최댓값·최솟값의 위치와 첫 다섯 스냅샷으로 다시 계산한 SVD가 들어 있습니다. `verification_recheck_20261015.json`은 저장된 실행을 읽어서 재검사한 기록입니다. 원본 `.npz`, 요청, 응답, 로그 파일은 바꾸지 않았습니다.

릴리스의 전체 실행 압축 파일에는 다섯 조건의 폴더와 계산 필드가 들어 있습니다. 더 작은 근거 자료 ZIP은 일부 파일을 모은 것으로, 전체 실행 기록과 구분됩니다. 모델 가중치는 포함하지 않습니다.

## 참고

JSON, JSONL, RAW, 솔버 로그는 텍스트입니다. NPZ는 NumPy 배열이고, 표로 보려면 CSV를 쓰면 됩니다.
