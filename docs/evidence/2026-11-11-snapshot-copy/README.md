# 스냅샷 복사만 넣은 브랜치를 OpenFOAM 네 버전에서 확인 (2026-11-11)

요약: 영문 저장소의 브랜치 `pr/podfoam-snapshot-copy`는 솔버 넷의 `PythonComm.H`에서 문장 하나를 바꿉니다.
이 변경으로 PODFoam은 Python에 올바른 스냅샷을 넘깁니다. 저장된 U와 p는 OpenFOAM 8, v2012, v2106,
v2212에서 원본 PODFoam과 바이트까지 같습니다.

브랜치는 `8d29128`이며 argonne-lcf/PythonFOAM `6fde869` 위의 커밋 둘입니다. `74e6450`은 PODFoam을,
`8d29128`은 `PODFoam_Debug`, `APMOSFoam`, `AEFoam`을 고칩니다. 파일마다 12줄이 늘어납니다. NumPy가
스냅샷 배열을 만들고 솔버가 버퍼를 그 배열에 복사합니다. 원본 코드는 Python에 그 버퍼의 뷰를 넘겼고,
다음 시간 단계가 그 버퍼를 덮어썼습니다.

## 실행

MedicineBow의 Slurm 작업 25191171–25191174, 2026-11-11, 버전마다 하나입니다([sacct.txt](sacct.txt)).
작업마다 PODFoam을 `6fde869`와 브랜치에서 한 번씩 빌드하고, 케이스 하나를 세 가지로 돌립니다.

| 기록의 이름 | 솔버 | `python_module.py` |
|---|---|---|
| `recording` | 원본 | 제공된 모듈. SVD에 넘기는 스냅샷 행렬을 모두 저장하게 함 |
| `copy` | 원본 | 위와 같고, Python에서 스냅샷마다 복사 |
| `ported` | 브랜치 | `recording`과 같음 |

OpenFOAM 8에서는 제공된 `Run_Case`를 `endTime` 1.5e-4로 돌렸고, 시간 단계는 221개, SVD 구간은 둘입니다.
v2012, v2106, v2212에서는 제공된 케이스가 발산하므로 연결 검증의 설정을 썼습니다. 시간 간격은 1e-7로
고정했고, 시간 단계는 60개, SVD 구간은 셋입니다.

## 결과

| 버전, 작업 | 행렬 수 | 첫 두 열이 같은 행렬: 원본 | 브랜치 | 브랜치 행렬이 Python 쪽 복사와 같음 | 세 실행의 U와 p가 같은 저장 시각 |
|---|---:|---:|---:|---|---|
| 8, 25191171 | 6 | 6 | 0 | 6개 모두 | 2개 중 2 |
| v2012, 25191173 | 9 | 9 | 0 | 9개 모두 | 3개 중 3 |
| v2106, 25191172 | 9 | 9 | 0 | 9개 모두 | 3개 중 3 |
| v2212, 25191174 | 9 | 9 | 0 | 9개 모두 | 3개 중 3 |

행렬 하나는 SVD 구간 하나의 속도 성분 하나입니다. "같다"는 바이트까지 같다는 뜻입니다.
빌드 8번이 모두 성공했고, 실행 12번이 모두 종료 상태 0으로 끝났으며 Python 오류 추적은 없었습니다.

## 나머지 세 솔버

작업 25191260–25191271이 `PODFoam_Debug`, `APMOSFoam`, `AEFoam`을 같은 세 가지로 돌렸습니다. 솔버마다
네 버전에서 `6fde869`와 브랜치로 빌드했습니다.

| 솔버 | 버전 | 행렬 수 | 첫 두 열이 같은 행렬: 원본 | 브랜치 | 브랜치 행렬이 Python 쪽 복사와 같음 | 세 실행의 U와 p가 같은 저장 시각 |
|---|---|---:|---:|---:|---|---|
| `PODFoam_Debug` | 8 | 6 | 6 | 0 | 6개 모두 | 2개 중 2 |
| `PODFoam_Debug` | v2012, v2106, v2212 | 각 9 | 9 | 0 | 9개 모두 | 3개 중 3 |
| `APMOSFoam`, MPI rank 4개 | 8 | 24 | 24 | 0 | 24개 모두 | 2개 중 2 |
| `APMOSFoam`, MPI rank 4개 | v2012, v2106, v2212 | 각 36 | 36 | 0 | 36개 모두 | 3개 중 3 |
| `AEFoam` | 8, v2012, v2106, v2212 | 각 1 | 1 | 0 | 1개 | 1개 중 1 |

`AEFoam` 실행은 모두 첫 스냅샷 행렬 뒤에 세그멘테이션 오류(종료 상태 139)로 끝납니다. OpenFOAM 8에서는
시간 단계 101개 뒤, 나머지에서는 21개 뒤입니다. 원본 코드와 브랜치 모두 그렇게 끝나므로, 표의 `AEFoam`
행은 버전마다 행렬 하나와 저장 시각 하나입니다.

## 원본 프로젝트의 Docker 이미지 안의 브랜치

작업 25191272가 rootless Podman으로 `romitmaulik1/pythonfoam_docker`를 받아, root로 이미지의 Python 3.6.9와
NumPy 1.19.5를 써서 브랜치의 솔버 넷을 빌드했습니다. 넷 모두 빌드되었습니다. 이어서 PODFoam이 제공된
`Run_Case`를 시간 단계 221개 동안 돌렸고, 스냅샷 행렬 6개 중 첫 두 열이 같은 것은 없습니다.
기록: [container/podman-small-25191272.txt](container/podman-small-25191272.txt).

## PR의 Docker 명령을 Podman으로 root에서 실행

Slurm 작업 25191239가 rootless Podman 5.2.5로 Docker Hub에서 `romitmaulik1/pythonfoam_docker`(다이제스트
`sha256:32a99155…d84c`)를 받아, pull request 글의 Docker 명령을 그 안에서 root(uid 0)로 돌렸습니다.
`validation/run.sh`는 영문 저장소의 `pr/podfoam-fix`(`473c802`)와 `pr/podfoam-observer`(`9e278aa`)에서 모두
`PASS`로 끝났습니다. 기록: [container/](container/).

이 클러스터에서는 Docker 데몬이 뜨지 않습니다. 작업 25191209는 "No subuid ranges found"에서 멈췄습니다.
Podman은 같은 `run` 명령을 받습니다. 같은 명령의 앞선 실행은 일반 사용자로 Apptainer를 썼습니다.

## 한계

- `AEFoam`은 첫 스냅샷 행렬에서만 확인했습니다. `AEFoam` 실행이 모두 그 행렬 뒤에 중단되기 때문입니다.
- v2012, v2106, v2212의 케이스는 제공된 케이스가 아니라 안정화한 케이스입니다.
- 실행은 짧습니다. 시간 단계는 OpenFOAM 8에서 221개, 나머지에서 60개입니다. 이 브랜치에는 검증 스크립트가 없고, `pr/podfoam-fix`에는 있습니다.

## 파일

- [scripts/](scripts/): PODFoam용 `small.sbatch`와 나머지 셋용 `sib.sbatch`, OpenFOAM 이미지 안에서 도는 `inner.sh`, `compare2.py`, 솔버마다 모듈 둘.
- [runs/](runs/): 작업마다 비교 결과인 `summary.txt`와 `result.json`, 브랜치의 `PythonComm.H`를 원본과
  견준 `branch.diff`, `BRANCH`, `UPSTREAM`, 빌드 로그 둘, `job.out`. 케이스 폴더는 작업마다
  156–348 MB이며 클러스터에 둡니다.
