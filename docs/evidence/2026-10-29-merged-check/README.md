# 10월 29일 근거: 합친 코드로 돌린 솔버 실행

MedicineBow Slurm 작업 24936949, 2026-10-29, CPU 노드 mbcpu-009, 7분 20초:
`eff951b`의 체크아웃(callback, instability-test, observer-3d 가지와
`record_written`을 합친 main; 커밋하지 않은 변경은 문서뿐, `git-status.txt`)을
OpenFOAM v2212 이미지에서 `validation/run_v2106.sh`로 빌드했습니다
([merged_check.sbatch](merged_check.sbatch)).

| 확인 | 결과 |
|---|---|
| 빌드와 연결 검증 | PASS ([validation.log](validation.log)) |
| 2D 계단 경우, 100걸음의 v2 프레임, 110걸음 | 프레임의 파일 넷(`U.png`, `p.png`, `fields.npz`, `readable-metadata.json`)과 요청 본문이 2026-10-27 MPI 시험(작업 24903786)의 직렬 실행과 같음; `telemetry.jsonl` 110줄, `.tmp` 남지 않음 |
| 단면 시험의 3D 경우, 100걸음의 v2 프레임, 110걸음 | 단면(z = 0.00714375 m의 칸 20,540개), 프레임의 파일 넷과 요청 본문이 작업 24929629의 직렬 3D 실행과 같음; `telemetry.jsonl` 110줄, `.tmp` 남지 않음 |

숫자는 [merged-check.json](merged-check.json)에서 왔고, 솔버 로그는
`serial2d/log.PODFoam.gz`와 `serial3d/log.PODFoam.gz`입니다. 모델에는 묻지
않았습니다(`LLM_ENABLED=0`). 실행 폴더는 클러스터의
`/cluster/medbow/gscratch/syome/github_repos/pod-merged-20261029/run-24936949`에
남아 있습니다. [manifest.json](manifest.json)에 여기 있는 모든 파일의 크기와
해시가 있습니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-29-merged-check/README.md)
