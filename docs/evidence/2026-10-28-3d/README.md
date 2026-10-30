# 10월 28일 근거: 3D 경우의 v2 관찰 그림, 평면 단면으로

MedicineBow(와이오밍 대학교)에서 2026-10-28에 돌린 솔버 실행입니다. 작업마다 CPU 노드 하나에서, OpenFOAM
v2212(Apptainer 이미지 `of2212.sif`)의 PODFoam과 v2 그림을 쓰는 관찰 기능을 모델 없이(`LLM_ENABLED=0`)
돌렸습니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-28-3d/README.md)

## 바뀐 것

지금까지 v2 그림은 2D 경우의 empty 패치에서 칸마다 다각형 하나를 얻어야 했고, 3D 경우는 거부했습니다.
이제는(커밋 `07759b0`과 `127a1dc`):

- `PythonSlice.H`가 3D 격자(empty 패치 없음)를 OpenFOAM의 `cuttingPlane`으로 z = `LLM_SLICE_Z`에서 자릅니다.
  기본값은 격자 z 범위의 가운데이고, 법선은 (0 0 1)이며, 삼각형으로 나누지 않습니다: 잘린 칸마다 다각형 하나,
  곧 그 칸의 단면입니다. 격자 점을 지나는 평면은 두 칸 사이의 면 위에 놓이므로, 위쪽의 다음 점 평면까지
  절반만큼 옮깁니다. `PythonCreate.H`는 다각형을 기존 `mesh_func` 인자로(rank마다 칸 오프셋, master로 모음)
  넘기고, 여덟 번째 인자로 평면을 설명합니다. 2D 경우는 예전처럼 인자 일곱 개로 호출됩니다.
- Python(`pod_image.plane_slice`, `python_module.py`, `readable_request.render_frame`): 3D 경우의 v2 프레임은
  단면 칸만 담습니다. `fields.npz`에는 그 칸들의 중심(3D 칸 중심), U, p와 함께 `mesh_cells`, `polygon_points`,
  `polygon_offsets`가 들어가고, `readable-metadata.json`에는 `slice`가 들어갑니다. 요청은 2D와 같이 만듭니다.

## 작업

| 작업 | 내용 | 코드 | 결과 |
|---|---|---|---|
| 24929463, 24929474 | 컴파일 확인(wmake만; 그 스크립트는 남기지 않음) | `07759b0` 전의 작업 트리 | 24929463은 실패(`MeshedSurface.H`를 찾지 못함: `Make/options`에 surfMesh include가 없었음); 24929474는 경고 없이 컴파일됨 |
| 24929484 | 단면 시험, 첫 시도 | `07759b0` | 작업 자체의 칸 대응 확인에서 멈춤: 허용 오차(10⁻¹² m)가 저장한 칸 중심의 정밀도보다 작았음(차이 1.0×10⁻¹¹ m); [출력](slice-test-24929484.out) |
| 24929500 | 단면 시험 | `07759b0` | 모든 확인 통과; `LLM_SLICE_Z=abc` 실행의 기하 줄이 단면을 만들지 않았는데도 `slice z=0`이라고 적음(`127a1dc`에서 고침); [출력](run-24929500/slice-test-24929500.out), [비교](run-24929500/frame-comparison.json) |
| 24929629 | 단면 시험, 최종 코드 | `c7a25d3`(`127a1dc`의 코드) | 아래 결과; [출력](slice-test-24929629.out) |

작업 출력과 실행 폴더는 클러스터의 `/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/`에 남아
있습니다. 최종 실행은 그 안의 `run-24929629`입니다(시각 폴더, 프레임, 요청 기록, 로그).

## 3D 경우

- [make_case3d.py](make_case3d.py)로, 준비해 둔 2D 계단 경우(칸 20,540개, t = 0.1 s의 발달한 흐름,
  2026-10-27 MPI 시험의 경우)에서 만들었습니다: 그 `blockMeshDict`에서 z 방향 칸을 1개 대신 8개로 하고(z는
  0\~0.0127 m, 2D 격자의 두께), 앞뒤 패치를 `empty`에서 `wall`로 바꿨습니다. 칸 164,320개.
- checkMesh([로그](case3d/log.checkMesh))는 확인 하나, 큰 종횡비에서 실패합니다: 최대 7601.13, 칸 1,536개
  (8 × 192). 연결 검증의 2D 격자도 칸 192개에 대해 같은 최대 비를 보고합니다(그 checkMesh 로그는 클러스터의
  `run-24929629/pod-v2212.x73dcD/`에 있음).
- 시작 상태: t = 0.1 s 2D 경우의 U와 p를 8개 층마다 복사하고, Uz = 0; 경계 조건은 2D와 같고, 앞뒤는 미끄럼
  없는 벽(p는 zero gradient). 칸 대응은 OpenFOAM의 칸 중심으로 확인했습니다
  ([case3d-check.json](case3d-check.json)): 2D 칸마다 8칸, x와 y가 1.0×10⁻¹¹ m 안에서 같음(중심은 12자리로
  저장; 가장 가까운 2D 중심 둘은 1.2×10⁻⁵ m 떨어져 있음).
- 이 시작 상태는 발달한 3D 흐름이 아닙니다: 앞뒤 벽은 t = 0.1 s에 작용하기 시작하고, 실행은 5×10⁻⁶ s 간격
  150걸음입니다.

## 실행

모두 `LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1
LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04`
(다른 값은 줄마다), t = 0.1 s부터 시간 간격 5×10⁻⁶ s, BLAS 스레드 하나.

| 경우 | rank | 걸음 | 관찰 기능 | 단면 | 저장 |
|---|---|---|---|---|---|
| `serial3d` | 1 | 150 | 있음 | 기본 | 50걸음마다 |
| `par3d` | 2, scotch | 150 | 있음 | 기본 | 50걸음마다, 재구성 |
| `noobs3d` | 1 | 150 | 없음: `python_module.py`가 POD 모듈, `analysis_func` 없음 | 없음 | 50걸음마다 |
| `slicez3d` | 1 | 10, 걸음 5에 프레임 | 있음 | `LLM_SLICE_Z=0.002` | 안 함 |
| `badz3d` | 1 | 4, 걸음 2에 요청 | 있음 | `LLM_SLICE_Z=abc` | 안 함 |
| `outz3d` | 1 | 4, 걸음 2에 요청 | 있음 | `LLM_SLICE_Z=1.0` | 안 함 |
| `serial2d` | 1 | 120 | 있음 | 2D 경우, 단면 없음 | 안 함 |

연결 검증(`validation/run_v2106.sh`, 2D, 열 걸음)을 같은 빌드로 먼저 돌렸습니다.

## 결과

다른 파일을 적지 않으면 [frame-comparison.json](frame-comparison.json)([compare_3d.py](compare_3d.py)가 씀)에서
온 것입니다.

- **단면.** z 범위의 가운데 0.00635 m는 (z = 0부터 세어) 넷째와 다섯째 칸 층 사이의 점 평면 위에 있으므로,
  평면은 다섯째 칸 층의 가운데인 0.00714375 m로 옮겨졌습니다. 평면은 2D 칸마다 하나씩 칸 20,540개를 자르고,
  그 중심은 모두 z = 0.00714375 m에 있습니다(5×10⁻¹⁸ m까지). 프레임은 칸 164,320개 중 그 20,540개를 담습니다.
- **직렬과 rank 2개.** 같은 칸 20,540개입니다(decomposePar의 `cellProcAddressing`을 거쳐 격자 칸 번호로 맞추고
  중심으로 정렬). 중심은 4.2×10⁻¹⁷ m까지 같고, 다각형 꼭짓점은 같습니다(다각형마다 꼭짓점을 정렬). U는
  2.5×10⁻³ m/s(가장 큰 성분 37.2 m/s) 안, p는 0.036 m²/s²(가장 큰 |p| 282) 안으로, 병렬 계산의 차이입니다.
  두 rank는 단면 칸을 10,293개와 10,247개 가졌습니다.
- **저장한 필드와 프레임 비교**, t = 0.1005 s(걸음 100): 저장 파일의 12자리 안에서 같습니다(가장 큰 상대 차이
  4.9×10⁻¹²). 직렬과 재구성한 rank 2개 실행 모두 그렇습니다.
- **관찰 기능 있음과 없음.** 저장한 시각 폴더 세 개의 파일 63개(U, p, phi, POD 모드 파일, `uniform/time`)가
  모두 같습니다.
- **프레임을 읽는 도구.** `readable_request.load_frame`(모든 해시 확인)과 `picture_test.load_v2`(정답)가 단면
  프레임을 읽습니다. 콜백이 쓴 요청 본문은 프레임에 `describe_v2_payload`를 적용한 것과 같습니다. 요청 메모는
  2D와 같이 칸 20,540개와 그린 범위를 줍니다. 정답: 가장 빠른 곳은 27.5 % / 42.3 %(그린 범위의 x / y), 가장
  낮은 압력은 31.0 % / 25.5 %.
- **`LLM_SLICE_Z=0.002`.** 격자 점 위가 아니어서 옮기지 않음; 칸 20,540개, 중심은 z = 0.00238125 m(둘째 층).
- **거부.** `LLM_SLICE_Z=abc`: 솔버 경고 "No plane slice for the observer: LLM_SLICE_Z is not a finite number:
  'abc'", 기하 줄 `slice none`; 걸음 2의 요청은 `callback_error`("v2 pictures of a 3D case need a plane slice:
  no plane slice: ...")로 끝납니다. `LLM_SLICE_Z=1.0`: 평면이 어떤 칸도 자르지 않아, 솔버 경고 "The
  observer's plane slice z=1 cuts no cells; v2 pictures will be refused", `callback_error`("... the plane z = 1
  m cuts no cells"). 두 실행 모두 끝까지 돌았습니다(frame-comparison.json의 `runs`, 로그는 `badz3d/`,
  `outz3d/`).
- **2D는 그대로.** 연결 검증을 통과합니다([validation.log](validation.log)). 걸음 100의 2D 프레임은 2026-10-27
  MPI 시험(작업 24903786)의 직렬 프레임과 파일 하나하나(`U.png`, `p.png`, `fields.npz`,
  `readable-metadata.json`)까지 같고, 요청 본문도 같습니다.
- **반복.** 프레임 파일, 요청 본문, 저장 파일이 모두 작업 24929500과 24929629 사이에서 같습니다: `serial3d`와
  `par3d`에서 각각 68개 중 68개, `noobs3d`에서 63개, `slicez3d`와 `serial2d`에서 5개; 거부된 두 실행은 아무
  파일도 쓰지 않습니다([repeat-comparison.json](repeat-comparison.json), [compare_runs.py](compare_runs.py)로
  만듦).

## 그림

[U.png](serial3d/llm_observation/step-000100/U.png)와
[p.png](serial3d/llm_observation/step-000100/p.png): 걸음 100의 직렬 단면 프레임, 계단 뒤 x 0\~0.12 m, y
0\~0.04 m를 그린 것.

눈으로 보았습니다: 제대로 보입니다. 2D 그림처럼 칸마다 한 색의 평평한 조각입니다. 그림은 같은 걸음의 2D
프레임에서 본 계단 흐름을 보여 줍니다: 전단층이 높이의 약 32 %에서 계단 모서리를 떠나고(계단은 0.04 m 중
0.0127 m), 그 위에 빠른 흐름과 x = 28 %와 60 % 근처의 밝은 점 두 개, 아래에 느린 재순환 흐름, x = 31 %와
60 % 근처에 낮은 압력의 중심이 있습니다. 창 안의 가장 큰 |U|는 37.24 m/s(2D 37.21)입니다. 압력 색 막대는
다릅니다: 단면 그림은 −281.6\~90.9 m²/s², 2D 그림은 −335.0\~43.9(`serial3d/llm_result.json`과
`serial2d/llm_result.json`의 `colour_range`); 단면 전체에서 p는 2D 프레임과 최대 213 m²/s²까지 다릅니다
(`slice_vs_2d_frame`). 3D 경우에는 앞뒤에 마찰이 있는 벽이 있고 출구 압력은 고정되어 있으므로, 상류 압력이
올라갈 것입니다; 이 시험은 그 물리를 확인하지 않습니다. rank 2개 그림도 같아 보이고, z = 0.002 m 단면(걸음 5,
여기 남기지 않음)도 그 이른 시각에 같은 구조를 보입니다. 그림과 요청 어느 쪽도 단면을 보여 준다고 말하지
않습니다. 프레임 메타데이터가 말합니다.

## 시험하지 않은 것

- 이 격자만 해 봤습니다: z로 밀어낸 육면체, z에 수직인 평면. 다면체나 사면체 격자, 볼록하지 않은 칸, 비정렬
  격자의 점을 지나는 평면, 다른 방향의 단면은 해 보지 않았습니다. `cuttingPlane`은 자를 수 없는 칸을
  건너뜁니다("Failed cuts" 경고; 여기서는 없음). 그런 칸은 그림에서 흰 구멍이 될 것입니다.
- 모델에게 묻지 않았습니다: 모델이 단면 그림을 얼마나 잘 읽는지는 여기서 알 수 없습니다.
- 3D 흐름 자체: 벽을 더한 2D 상태에서 150걸음 돌린 것이지, 검증한 3D 해가 아닙니다.
- 솔버에서 3D 경우의 sequence 모드와 v1 그림(sequence: 합성 기하로 단위 테스트만; v1은 래스터를 그대로 쓰며,
  돌리지 않음).
- v2212가 아닌 OpenFOAM 버전(코드는 v2106이나 openfoam.org용으로 컴파일하지 않았음; `PythonSlice.H`는 모든
  빌드에 들어가므로, v2106에서 컴파일이 실패하면 2D 경우도 영향을 받음), rank 2개 넘게, 노드 하나 넘게.
- 쐐기(wedge) 격자, 그리고 대칭이나 cyclic 패치로 둘러싸인 한 층 격자: 이들은 `empty` 패치가 없어서 z
  가운데에서 잘릴 것입니다. 칸 크기가 고르지 않은(graded) 격자나 비정렬 격자에서는 평면을 위쪽의 가장 가까운 점
  평면까지 절반만큼 한 번 옮기고, 다시 확인하지 않습니다.
- 이 브랜치보다 오래된 `python_module.py`: 그 `mesh_func`는 인자 일곱 개를 받아 여덟 번째에서 실패하므로, 그런
  3D 경우는 그림을 얻지 못합니다(이 브랜치 전의 `main`에서는 v1 래스터를 얻었음).
- 2026-10-29의 검토(작업 24936879, 24936904, 24936930)에서 비교를 다시 돌렸고(같은 결과), rank 하나가 칸을
  하나도 자르지 않는 rank 2개 경우(z 방향 분할로 `LLM_SLICE_Z` 0.002와 0.012)를 돌렸습니다: 프레임이
  맞았습니다. 그 검토는 필드를 5걸음마다보다 자주 쓰면 PODFoam이 두 번째 SVD에서 멈춘다는 것("Expected SVD
  shape")도 찾았습니다. 이것은 이미 `main`에 있는 문제이고, 여기 실행(50걸음마다 저장)과는 관계가 없습니다.

## 파일

| 경로 | 내용 |
|---|---|
| `slice_test.sbatch`, `slice_test_inner.sh` | 제출한 그대로의 작업 스크립트(Slurm 24929629): 빌드와 검증, 3D 경우, 실행 일곱 개, 비교 |
| `make_case3d.py` | 3D 경우를 만듦: `blockMeshDict`, 시작 필드, 칸 대응 확인 |
| `compare_3d.py`, `frame-comparison.json` | 위의 확인과 그 결과 |
| `compare_runs.py`, `repeat-comparison.json` | 작업 24929500과 24929629를 파일마다 비교 |
| `case3d-check.json`, `case3d/` | 칸 대응 확인; 3D `blockMeshDict`, blockMesh와 checkMesh 로그 |
| `slice-test-24929629.out`, `validation.log`, `HEAD`, `git-status.txt`, `changes.patch` | 작업 출력, 연결 검증 로그, 작업이 본 코드 상태 |
| `serial3d/` | 솔버 로그(gzip), 요청과 결과 기록, 프레임의 그림 두 장과 메타데이터(`fields.npz`는 클러스터에 남음) |
| `par3d/` | 솔버 로그(gzip), 결과 기록, 프레임 메타데이터, 분할 설정과 로그 |
| `noobs3d/`, `slicez3d/`, `badz3d/`, `outz3d/`, `serial2d/` | 솔버 로그(gzip); 결과 기록(관찰 기능이 없는 `noobs3d`는 없음); `slicez3d`의 프레임 메타데이터 |
| `run-24929500/` | `07759b0`로 끝까지 돈 실행의 출력과 비교 |
| `slice-test-24929484.out` | 첫 시도의 출력 |
| [manifest.json](manifest.json) | 이 폴더 파일들의 출처, 크기, 해시 |

## 참고

- 작업은 POD 모듈의 audit 파일(`python_svd_audit.npz`, 경우마다 약 200 MB)을 지웠습니다. 기록에는 출처를
  보이려고 클러스터 경로와 프로세스 번호가 남아 있습니다.
- `git-status.txt`는 `llm_demo/README.md`를 수정됨으로 적습니다: 3D 경우에 대한 그 설명은 작업이 도는 동안
  썼고, 실행에 영향을 주지 않습니다.
- rank 2개 경우의 POD 모듈은 자기 사본에서만 고쳤습니다(rank 확인, 2026-10-27 MPI 시험처럼;
  `slice_test_inner.sh` 참고).
- 3D 실행의 첫 걸음들은 벽이 작용하기 시작하면서 느립니다(PDE 계산이 걸음당 최대 38 s; 직렬 150걸음의
  중앙값은 2.84 s). 그래서 `badz3d`와 `outz3d`의 걸음 2에서 거부된 요청의 결과는 27.5 s 뒤인 걸음 3에서
  거두었습니다.
