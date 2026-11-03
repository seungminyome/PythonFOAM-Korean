# PODFoam의 선택형 Python 훅

PODFoam은 케이스 폴더의 `python_module.py`를 불러옵니다. 모듈은 함수 두 개를 정의해야 하며,
그러지 않으면 솔버가 시작할 때 멈춥니다.

- `snapshot_func(array, rank)`는 스냅샷을 모을 때마다 이 rank의 U를 `(cells, 3)` float64
  배열로 받습니다.
- `svd_func(rank)`는 모드를 시스템 기본 바이트 순서의 float64 ndarray로 돌려줍니다. 모양은
  `(3*cells, modes)`이고 모드는 하나 이상입니다. u 모드가 앞의 `cells`개 행을 채우고, v와 w가
  그 뒤를 잇습니다. 솔버는 앞의 `podTruncation`개 모드를 씁니다. `podTruncation`은
  `controlDict` 항목이고 기본값은 5입니다.

두 함수의 예는 제공된 `Run_Case/python_module.py`에 있습니다. 반환값의 조건 전체는
[validation/README.md](validation/README.md)에 있습니다.

함수 두 개를 더 둘 수 있습니다.

- `mesh_func(centres, volumes, solution_d, rank, poly_points, poly_offsets,
  poly_cells[, slice_plane])`는 `analysis_func`가 있을 때 시작 시점, 첫 시간 단계 전에 한 번
  실행됩니다.
- `analysis_func(state)`는 시간 단계마다 한 번, PIMPLE 반복과 POD 단계 뒤, `runTime.write()`
  전에 실행됩니다. 저장 단계에서는 호출하는 동안 그 시각의 U와 p가 아직 디스크에 없습니다.

두 함수는 U도 p도 바꾸지 않습니다. `analysis_func`를 정의하면 POD 단계가 모든 시간 단계에서
스냅샷을 모읍니다. 아래 "POD 일정"에서 설명합니다.

## `mesh_func`의 인자

셀 배열은 모두 격자 전체를 담고 rank 순서로 모읍니다. 직렬 실행에서는 격자의 셀 순서를
그대로 씁니다.

| 인자 | 자료형과 모양 | 뜻 |
|---|---|---|
| `centres` | float64 `(cells, 3)` | 셀 중심, m |
| `volumes` | float64 `(cells,)` | 셀 부피, m³ |
| `solution_d` | 정수 3개의 튜플 | `mesh.solutionD()`: 푸는 방향은 1, 빈 방향은 -1 |
| `rank` | int | 항상 0: 마스터 rank만 훅을 부릅니다 |
| `poly_points` | float64 `(P, 3)` | 모든 다각형의 점, 다각형 순서대로 |
| `poly_offsets` | int64 `(F + 1,)` | 다각형 `i`의 점은 `poly_offsets[i]:poly_offsets[i+1]`; `poly_offsets[0]`은 0 |
| `poly_cells` | int64 `(F,)` | 각 다각형의 셀, `centres`의 색인 |
| `slice_plane` | dict | `empty` 패치가 없는 격자에서만, 아래 참조 |

`slice_plane`의 키는 다음과 같습니다.

- `normal`: 항상 `(0.0, 0.0, 1.0)`.
- `z_m`: 자른 평면의 z.
- `requested_z_m`: `POD_SLICE_Z`, 또는 z 범위의 가운데.
- `z_source`: `"POD_SLICE_Z"` 또는 `"middle of the mesh z range"`.
- `moved_off_mesh_points`: bool.
- `mesh_z_range_m`: `(z_min, z_max)`.

자르지 못했을 때는 `normal`, None인 `z_m`, `z_source`, 메시지를 담은 `error`,
`mesh_z_range_m`이 들어 있습니다.

## `state`

| 키 | 자료형 | 뜻 |
|---|---|---|
| `schema_version` | int | 1 |
| `time_s`, `delta_t_s`, `end_time_s` | float | 이 단계의 시각, 시간 간격, 끝 시각, s |
| `step` | int | OpenFOAM의 시간 색인; 재시작하면 이어서 셉니다 |
| `snapshot_count` | int | 이 실행이 지금까지 모은 스냅샷 수, 이 단계 포함; 0초에서 시작하면 `step`과 같습니다 |
| `cells` | int | 격자 전체의 셀 수 |
| `residuals` | dict | 필드 `Ux`, `Uy`, `Uz`, `p`마다 이 단계의 실수 `initial_first`, `initial_last`, `final_last`와 정수 `linear_solves`, `iterations_total` |
| `courant` | dict | 끝난 단계의 `phi`로 다시 계산한 `mean`, `max`, 그리고 `phase` |
| `continuity` | dict | `local`, `global`, `cumulative`, `phase` |
| `p_cells` | float64 `(cells,)` | 모든 셀의 운동학적 압력, m²/s² |
| `u_cells` | float64 `(cells, 3)` | 모든 셀의 속도, m/s |

`residuals`에서는 빈 방향을 뺍니다. 운동량 예측자를 끄면 U도 뺍니다. `p_cells`와 `u_cells`는
`centres`와 같은 순서입니다. 이 배열을 할당하지 못하면 호출은 둘 없이 계속됩니다.

OpenFOAM 8에서는 `residuals`에 한계가 두 가지 더 있습니다. 그곳의 `Residuals<Type>`은 한 형식,
곧 스칼라나 벡터의 목록을 시간 단계에서 그 형식을 처음 풀 때 비웁니다. 시간 단계에서 풀이가
없는 필드는, 예를 들어 `maxIter 0`이면, 같은 형식의 다른 필드를 풀지 않는 한 이전 단계의 목록을
그대로 둡니다. 격자가 움직이면 목록이 지워집니다. 움직이는 격자에서
`moveMeshOuterCorrectors`를 쓰면 목록에는 마지막 외부 보정의 풀이만 남습니다.
`initial_first`, `linear_solves`, `iterations_total`도 그 보정의 풀이만 셉니다.

## 동작

배열은 모두 복사본이므로 Python은 솔버 메모리를 보지 않습니다. `analysis_func`의 반환값은
무시합니다. `analysis_func`에서 예외가 나면 경고가 나오고 실행은 계속되며, 다음 시간 단계에서
훅을 다시 부릅니다. `mesh_func`에서 예외가 나면 경고가 나오고, `analysis_func`는 격자 정보 없이
실행됩니다. `analysis_func`나 `mesh_func`를 호출할 수 없는 모듈은 경고 한 줄을 받고, 그 훅 없이
실행됩니다.

**시간 단계마다 드는 비용.** `analysis_func`를 정의하면 모든 rank가 매 시간 단계 U와 p를 마스터
rank로 보냅니다. 마스터는 모듈이 쓰든 쓰지 않든 이를 새 배열 두 개와 딕셔너리 하나에 복사합니다.
Courant 수와 연속 방정식 수치에는 면 합산과 `phi`의 발산 계산이 더해집니다. 큰 병렬 케이스에서는
마스터가 매 시간 단계 격자 전체의 U와 p를 들고 있습니다.

**스레드.** 솔버는 Python 호출 바깥에서 인터프리터 잠금을 쥐고 있습니다. 모듈이 시작한 스레드는
솔버가 그런 호출 안에 있을 때만 돌아갑니다. 이런 호출에는 `python_module`을 가져오는 일, 네
함수, 끝의 `Py_FinalizeEx()`가 들어갑니다. `Py_FinalizeEx()`는 데몬이 아닌 스레드를 기다리므로,
그런 스레드를 시작한 모듈은 스레드를 멈추기도 해야 합니다.

**부동소수점 트랩.** 트랩은 `PythonCreate.H` 전체와 시간 단계마다의 `PythonComm.H` 블록에서
꺼져 있습니다. 까닭은 [validation/README.md](validation/README.md)에 있습니다. 이 블록에는 격자
모으기, 평면 자르기, 시간 단계마다의 모으기, Courant 수와 연속 방정식 수치 계산도 들어 있으므로,
이 계산도 트랩 없이 돌아갑니다.

**병렬 실행.** 마스터 rank가 격자, U, p를 rank 순서로 모으고, 두 훅은 마스터만 부릅니다.
모든 rank의 모듈이 두 훅을 정의하거나, 어느 rank도 정의하지 않아야 합니다. 그렇지 않으면
실행은 시작할 때 멈춥니다. `snapshot_func`와 `svd_func`는 rank마다 따로 실행됩니다.

**셀 다각형.** `empty` 패치가 있는 케이스는 첫 `empty` 패치에 면이 있는 셀마다 그 면으로 다각형
하나를 넘깁니다. 그런 면이 없는 셀은 다각형을 받지 않습니다. 앞면과 뒷면을 함께 담은 패치는 셀을
두 번씩 나열하므로, 셀마다 첫 면만 남깁니다.

**`empty` 패치가 없는 격자.** 3D 격자에는 `empty` 패치가 없습니다. `PythonSlice.H`가 이런
격자를 평면 z = `POD_SLICE_Z`로 자릅니다. 기본값은 z 범위의 가운데입니다. 잘린 셀마다 다각형
하나와 `slice_plane`을 넘깁니다. 평면이 격자 점을 지나면 점에서 비켜 놓고, 솔버 로그에 그렇게
적습니다. 이 선택은 패치 종류만 보므로, `wedge` 패치가 있고 `empty` 패치가 없는 2D 축대칭
케이스도 자릅니다.

**POD 일정.** `podSvdInterval`이 기본값 0이면, `analysis_func`가 없는 모듈은 모든 시간 단계에서
스냅샷을 모읍니다. 예외는 마지막 SVD 뒤에 모은 스냅샷이 있는 저장 단계이며, 그곳에서는 대신
SVD가 실행됩니다. `analysis_func`가 있는 모듈은 모든 시간 단계에서 스냅샷을 모으고, SVD는 저장
단계에서 실행됩니다. 이 기본값에서는 두 모듈의 SVD 구간과 모드 파일이 다릅니다.
`podSvdInterval`이 0보다 크면 `analysis_func`가 있든 없든 모든 시간 단계에서 스냅샷을 모으고,
SVD는 스냅샷 `podSvdInterval`개마다 실행됩니다. U와 p는 어느 경우에도 같습니다.
