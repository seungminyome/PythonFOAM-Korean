# PODFoam의 C++·Python 연결 검증

스크립트 `validation/run.sh`는 셀 20,540개인 PODFoam 케이스를 직렬로 10단계 실행하고, C++와 Python
사이의 자료 왕복을 확인합니다. 이 문서에서는 이 확인을 연결 검증이라고 부릅니다. 스냅샷은 하나하나
독립된 배열로 Python에 도착해야 합니다. NumPy는 속도 성분마다 SVD 모드 5개를 돌려주고, 그 모드는
OpenFOAM 필드로 돌아와야 합니다. 솔버는 정상 종료해야 합니다. 스크립트는 케이스의 복사본에서 실행하며,
제공된 케이스 `Run_Case`는 바꾸지 않습니다.

```bash
cd Solver_Examples/PODFoam
./validation/run.sh                      # new directory validation/runs/pod-<version>.XXXXXX
./validation/run.sh --resume <run-dir>   # reuse the mesh and the pimpleFoam run
./validation/run.sh --baseline           # also run the shipped case with pimpleFoam (recorded only)
./validation/run.sh --baseline --resume <run-dir>   # both; --baseline comes first
```

스크립트는 openfoam.com의 v2012, v2106, v2212와 openfoam.org의 OpenFOAM 8을 지원합니다.
스크립트는 이미 source한 OpenFOAM이 있으면 그 OpenFOAM을 쓰고, 없으면 v2106을 씁니다. 다른 설치를
쓰려면 `OPENFOAM_BASHRC`에 그 설치의 bashrc를, `POD_OPENFOAM_VERSION`에 그 설치가 알리는
`WM_PROJECT_VERSION`을 지정합니다. 두 값이 맞지 않으면 스크립트는 방금 만든 실행 폴더를 지우고
멈춥니다. 실행 폴더 이름에는 버전이 들어갑니다.

```bash
OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212 ./validation/run.sh
OPENFOAM_BASHRC=/opt/openfoam8/etc/bashrc POD_OPENFOAM_VERSION=8 ./validation/run.sh
```

환경 변수 `PYTHON`은 Python 3 인터프리터를 가리키며 기본값은 `PATH`의 `python3`입니다. 스크립트가
`PYTHONNOUSERSITE=1`을 설정하고 `PYTHONPATH`를 지우므로, 그 인터프리터 자신의
site-packages에 numpy가 있어야 합니다. 시스템 Python이 아닌 인터프리터를 쓰면 그 인터프리터의 `lib`
폴더를 `LD_LIBRARY_PATH`에 넣어야 하며, 그러지 않으면 스크립트가 `Unresolved shared libraries`에서
멈춥니다. `POD_WORKSPACE`는 실행 폴더를 둘 곳입니다. 기본값은 `validation/runs/`이고
`.gitignore`가 이 폴더를 제외합니다.

스크립트는 `FOAM_USER_APPBIN`을 실행 폴더의 `bin/`으로 지정하므로 사용자의 애플리케이션
폴더에는 파일을 쓰지 않습니다. 스크립트는 `PYTHONUNBUFFERED=1`도 설정합니다. 이 변수가 없으면
`log.PODFoam`에 들어가는 Python `print()` 출력이 블록 단위로 버퍼링됩니다. 그러면 Python 출력은 솔버가
쓴 줄과 어긋난 채 조각으로 로그에 들어갑니다. 실행이 비정상 종료하면 버퍼에 남은 출력은 사라집니다.
Python은 버퍼 크기를 파일 시스템의 블록 크기로 정합니다. 이 검증을 시험한 클러스터의 스크래치 파일
시스템은 블록 크기가 1 MB입니다. 그래서 이 변수가 없으면 그 파일 시스템에서는 검증 실행의 출력이 끝에 한
조각으로 나타납니다. 블록 크기가 4 KB인 로컬 디스크에서는 이 변수가 없을 때 출력이 몇 KB마다 나타납니다.
`Run_Case/Allrun`이나 직접 시작한 PODFoam처럼 스크립트 밖에서 실행할 때도 이 변수나
`print(..., flush=True)`가 필요합니다.

검증은 빌드를 포함해 코어 하나에서 약 1분 걸립니다. 검증은 네 버전 모두에서 Python 3.11로
통과했습니다. OpenFOAM 8에서는 최상위 README가 소개하는 Docker 이미지의 Python 3.6.9로도
통과했습니다.

## 스크립트가 하는 일

1. 스크립트는 제공된 케이스의 설정을 아래 표처럼 바꿔 안정화한 복사본 `fixed-pimple`을 준비하고, 이
   복사본을 `pimpleFoam`으로 실행합니다.
2. 스크립트는 같은 복사본에 이 폴더의 `python_module.py`를 넣어 `fixed-pod`를 준비합니다. 이어서 다시
   빌드한 PODFoam을 `podSvdInterval 10`으로 10단계 실행하고, 그 결과를 `fixed-pimple`의 결과와 비교합니다.
3. `--baseline`을 주면 스크립트는 `baseline-pimple`도 준비합니다. `baseline-pimple`은 제공된 케이스에
   `deltaT=1e-5`와 10단계를 고정한 `controlDict`를 생성해 넣은 복사본입니다. 스크립트는 이 복사본에서
   표준 `pimpleFoam`을 부동소수점 트랩을 끄고 실행합니다. openfoam.com에서는 스크립트가
   `FOAM_SIGFPE=false`를 설정합니다. openfoam.org에서는 이 변수에 빈 값을 포함해 어떤 값이 있든 트랩이
   켜지므로, 스크립트가 이 변수를 지웁니다. 스크립트는 이 실행의 결과를 `baseline-pimple/log.pimpleFoam`과
   `baseline-pimple/exit-status`에 기록만 합니다. openfoam.com에서 이 복사본의 실행은 최대 Courant
   수가 약 21에 이르고, 두 번째 단계에서 NaN을 냅니다. OpenFOAM 8에서는 이 실행이 10단계를 마칩니다.

| 설정 | `fixed-pimple`의 값 |
|---|---|
| 난류 | 층류 |
| 초기 U | `(32.2 0 0)` |
| 시간 간격 | 고정, `deltaT=1e-7` |
| 시간 적분 | Euler |
| 대류항 | upwind |
| 비직교 보정 | limited |
| 비직교 보정 횟수 | 2 |
| 압력 스무더 | `DICGaussSeidel` |
| 단계 | 10단계, 모든 단계 저장 |

`wmake`, `blockMesh`, `pimpleFoam`, PODFoam 가운데 하나가 실패하면 스크립트는 멈추고 읽어야 할
로그를 알려 줍니다.

스크립트는 준비한 복사본에서 제공된 파일 `0/uniform/time`을 뺍니다. 이 파일에는 재시작용 `deltaT`
1초가 들어 있습니다. `adjustTimeStep yes`이면 제공된 케이스는 첫 단계의 시간 간격을 `controlDict`가
아니라 이 파일에서 가져오고, `maxCo`가 이 시간 간격을 약 0.012초로 줄입니다.

이 파일이 있고 `endTime`이 약 0.006초보다 작으면, 단계가 하나도 없는 실행이 정상 종료로
끝납니다.

제공된 `Run_Case`는 `maxCo 1`로 시간 간격을 조절합니다. openfoam.com에서는 제공된 `Run_Case`가 이
변경이 있든 없든 약 90단계 안에 발산합니다.

케이스 설정은 `prepare_case.py`가 바꿉니다. `prepare_case.py`는 바꿀 문장을 `Run_Case`에서 찾지
못하면 멈춥니다. 이 폴더의 `python_module.py`는 연결 검증에 필요한 최소 모듈입니다. 이 모듈은 스냅샷
10개를 보관하고 성분마다 모드 5개를 돌려주며, 검사를 위해 스냅샷, 모드, 특이값을
`python_svd_audit.npz`에 씁니다.

## `verify.py`가 검사하는 것

두 실행 `fixed-pimple`과 `fixed-pod`에 모두 하는 검사:

- 로그에 1e-7 ... 1e-6초의 `Time =` 기록이 정확히 10개 있고, `End`로 끝나며, `FOAM FATAL`이
  없습니다.
- 로그 어디에도 `nan`이나 `inf`가 없습니다.
- 로그에 잔차 값이 80개 이상 있고, 모두 유한합니다.
- 반복 상한 1000회에 이른 선형 풀이가 없습니다.
- 최대 Courant 수가 1보다 작습니다.
- 시간 폴더 10개가 모두 있고, 그 안의 필드 파일은 모두 유한하며 내부 필드를 빠짐없이 담습니다.
- 저장 필드의 최대 |U|가 1000 m/s보다 작습니다.

`fixed-pod`에만 하는 검사:

- 로그에 `POD snapshot accepted` 줄 10개와 `deltaT = 1e-07` 기록 10개가 있습니다.
  `POD SVD returned to OpenFOAM: rows=61620 modes=5 finite=true` 줄과
  `Python finalized successfully` 줄도 있습니다.
- `python_svd_audit.npz`의 스냅샷 모양은 `(20540, 3, 10)`, 모드 모양은 `(61620, 5)`입니다.
  스냅샷, 모드, 특이값은 모두 유한합니다.
- Python이 보관한 스냅샷이 저장된 U 필드와 같습니다. 허용 오차는 rtol 1e-10, atol 1e-9입니다.
- 모듈이 쓴 특이값이 보관한 스냅샷을 따로 `np.linalg.svd`로 분해한 값과 같습니다. 허용 오차는
  rtol 1e-9입니다.
- 돌려준 모드는 정규 직교이고, 이 특이값으로 스냅샷 행렬의 고유값 관계를 만족하며, 저장된
  `upod_*`, `vpod_*`, `wpod_*` 필드와 같습니다.
- U와 p가 모든 시간 단계에서 `fixed-pimple`과 같습니다. 허용 오차는 rtol 1e-10, atol 1e-9입니다.
  openfoam.com에서는 아래 "openfoam.com의 U와 p"에서 설명하는 압력 솔버 선택이 이 결과의
  전제입니다.

모든 검사를 통과해야 스크립트가 `PASS`를 출력합니다. 통과한 실행의 값은 다음과 같습니다.

| 통과한 실행 | 값 |
|---|---|
| 최대 Courant 수 | 약 0.211, OpenFOAM 8에서 0.212 |
| 스냅샷 최대 오차 | 약 5e-11 |
| 모드 최대 오차 | 약 5e-13 |
| `fixed-pod`에서 확인한 필드 파일 | 45개 |

## 모듈이 갖춰야 할 것

PODFoam은 케이스 폴더의 `python_module.py`를 불러옵니다. 모듈은 함수 두 개를 정의해야 합니다.

- `snapshot_func(array, rank)`는 이 rank의 U를 `(cells, 3)` float64 배열로 받습니다.
- `svd_func(rank)`는 모드를 시스템 기본 바이트 순서의 float64 ndarray로 돌려줍니다. 모양은
  `(3*cells, modes)`이고 모드는 하나 이상입니다. u 모드가 앞의 `cells`개 행을 채우고, v와 w가
  그 뒤를 잇습니다.

두 함수 중 하나가 없거나 호출할 수 없으면 솔버는 시작할 때 멈춥니다. 솔버는 앞의
`podTruncation`개 모드를 씁니다. `podTruncation`은 `controlDict` 항목이고 기본값은 5입니다.
1보다 작은 값을 주면 실행이 시작할 때 멈춥니다.
모듈이 모드를 `podTruncation`개보다 많이 돌려주면 솔버는 로그에 경고 한 줄을 씁니다. 제공된 모듈의
예는 `Run_Case/python_module.py`입니다.

## PODFoam에서 달라지는 점

다음 변경은 결과를 바꿉니다.

- **POD 모드.** 이제 스냅샷은 NumPy가 소유하는 배열로 Python에 도착합니다. 이 변경 전의
  PODFoam은 다음 시간 단계가 덮어쓴 C++ 버퍼의 뷰를 넘겼습니다. 제공된 모듈은 SVD 구간의 첫
  스냅샷을 그런 뷰로 보관했으므로, 모든 스냅샷 행렬의 앞 두 열이 같았습니다. SVD 구간은 스냅샷을 모아
  SVD를 한 번 계산하는 묶음입니다. 이제 첫 열에 첫 스냅샷이 들어갑니다. OpenFOAM 8에서 그 덮어쓰기를
  Python에서 재현하면, 모든 모드의 셀 값이 변경 전 PODFoam의 값과 같습니다. openfoam.com에서는 U와 p도
  달라집니다. 아래 "openfoam.com의 U와 p" 항목을 보십시오.
- **모드 파일.** 솔버는 모드를 무차원 `zeroGradient` 필드로 씁니다. 변경 전 PODFoam은 모드를 U
  성분의 복사본에 넣어 썼습니다. 그 필드의 차원은 U의 차원이었고, 경계에는 U의 경계값을 그대로 둔
  `calculated` 패치가 있었습니다.
- **저장 단계의 POD 일정.** `podSvdInterval`이 0이면, 저장 단계는 마지막 SVD 뒤에 모은
  스냅샷이 있을 때 SVD를 실행합니다. 모은 스냅샷이 없으면 스냅샷을 모읍니다. 변경 전
  PODFoam은 모든 저장 단계에서 `svd_func`를 실행했습니다. 제공된 케이스는 100단계마다
  저장하므로, 제공된 케이스의 일정은 바뀌지 않습니다. `writeInterval 1`이거나 저장 단계가 두 번 이어지면, 전에
  SVD를 실행하던 저장 단계에서 이제 스냅샷을 모읍니다.
- **openfoam.com의 U와 p.** PODFoam의 압력 풀이는 v2012, v2106, v2212의 `pimpleFoam`처럼 마지막 보정의
  마지막 비직교 반복에서만 `pFinal`을 씁니다. 나머지 반복에서는 `p` 솔버를 씁니다. 이 케이스처럼
  외부 보정이 하나이면, 이 버전들에서 단순한 `pEqn.solve()`는 모든 보정에서 `pFinal`을
  고릅니다. openfoam.org의 `pimpleFoam`은 단순한 `pEqn.solve()`를 부르고 PODFoam도 그렇게
  합니다. OpenFOAM 8에서 U, p, phi는 변경 전 PODFoam의 U, p, phi와 바이트 단위로 같습니다.

다음 변경은 실행을 멈추게 하거나 동작을 바꿀 수 있습니다.

- **부동소수점 트랩.** 트랩은 `pimpleFoam`처럼 솔버에서 켜져 있습니다. `PythonCreate.H` 전체,
  시간 단계마다의 `PythonComm.H` 블록, 종료 구간에서는 트랩이 꺼집니다. NumPy가 불러올 때 컴퓨터의
  수치 한계를 알아보려고 일부러 오버플로를 일으키기 때문입니다. 이 블록들은 Python 호출 말고도
  U를 스냅샷에 복사하고 모드 필드를 씁니다. 트랩은 `PythonCompat.H`의 `PythonFpeOff`가 끄며,
  openfoam.com에서는 `sigFpe::ignore`입니다. 변경 전 PODFoam은 `argList`를
  `initialise=false`로 만들었습니다. 그러면 `argList::parse`의 신호 설정을 건너뛰므로 트랩이
  꺼져 있었습니다. 변경 전 PODFoam에서 오버플로가 난 뒤에도 계속되던 실행은 이제 SIGFPE로 멈춥니다.
- **호출 검사.** 모듈을 불러오지 못하거나, 함수가 없거나, `snapshot_func`나 `svd_func`에서
  오류나 `SystemExit`가 나면 솔버는 Python 트레이스백을 출력하고 멈춥니다. 스냅샷 전에 U와 p가
  유한해야 합니다. `svd_func`는 시스템 기본 바이트 순서의 float64 ndarray를 모양
  `(3*cells, modes)`로 돌려줘야 하며 모드는 하나 이상이어야 합니다. 쓰는 모드는 유한해야 합니다.
  검사마다 실행을 멈추는 메시지가 따로 있습니다. 받은 모양을 밝히는 메시지는 모양이 틀렸을 때의
  것뿐입니다. 짧은 시험에서 제공된 모듈의 `online_mode = False`는 `writeInterval` 3과 6에서
  `Non-finite SVD result`로 멈췄습니다. 아주 작은 음의 고유값이 `np.sqrt`에서 NaN이 되기
  때문입니다.
- **모드 수.** 앞의 `podTruncation`개 모드만 쓰며, 열이 더 많으면 실행마다 경고 한 줄이
  나옵니다. 변경 전 PODFoam은 이 개수를 `PythonCreate.H`에 5로 고정해 두었습니다.
- **고정된 셀 수.** 셀 수가 바뀌면 POD 단계가 `POD requires a fixed cell count`로 실행을
  멈춥니다. 변경 전 PODFoam은 시작할 때 버퍼를 한 번 할당했고 셀 수를 검사하지
  않았습니다.
- **병렬 실행.** 모드마다 경계 갱신이 rank 사이에서 자료를 주고받으므로, 모든 rank가 같은 수의
  모드를 써야 합니다. rank마다 쓰는 모드 수는 돌려준 모드 수와 `podTruncation` 가운데 작은
  쪽입니다. 개수가 다르면 실행이 이유를 밝히고 멈춥니다. 셀이 모드보다 적은 rank는 모드를 적게
  돌려주고 같은 메시지로 실행을 멈춥니다. 셀이 없는 rank는 다른 rank의 개수를 따릅니다.
- **Python 스레드.** `Py_FinalizeEx()`는 Python 함수 참조를 해제한 뒤 끝에서 실행됩니다.
  이 호출은 데몬이 아닌 스레드를 기다립니다. 그런 스레드를 시작한 모듈은 스레드를 멈추기도
  해야 하며, 그러지 않으면 솔버가 끝나지 않습니다. 종료할 때 Python 표준 입출력을 비우지
  못하면 오류가 아니라 경고가 나옵니다. 솔버는 Python 호출 바깥에서 인터프리터 잠금을 쥐고
  있으므로, 모듈이 시작한 스레드는 그 호출 동안에만 실행됩니다.
- **`sys.path`.** `-case`가 케이스의 모듈을 찾도록 케이스 폴더가 `sys.path`의 맨 앞에 옵니다. 실행을 시작한
  폴더는 그 뒤에 남습니다.
- **로그.** 솔버는 시간 단계마다 `Time =` 줄을 deltaT와 함께 출력하고, 검증이 이 줄을 읽습니다. 모은
  스냅샷마다 스냅샷 수와 시간을 담은 `POD snapshot accepted:` 줄이 나옵니다. SVD마다 행 수와 쓴
  모드 수를 담은 `POD SVD returned to OpenFOAM:` 줄이 나옵니다. 시간 측정 줄은 그대로 있습니다.
  `setRootCaseLists.H`가 OpenFOAM 배너와 머리말 전체를 출력합니다. `initialize python`부터
  시작하던 시작 줄 여섯 개 대신 `Python and NumPy initialized successfully` 한 줄이 나오고,
  `End` 앞에 `Python finalized successfully`가 나옵니다.

`podSvdInterval`은 새로 생긴 선택 `controlDict` 항목입니다. 기본값 0에서 저장 단계는 "저장 단계의 POD
일정"대로 SVD를 실행합니다. 0보다 크면 모든 시간 단계에서 스냅샷을 모으고, 스냅샷
`podSvdInterval`개마다 SVD를 실행합니다. 그러면 다른 것을 저장하지 않는 시간 단계의 SVD가 모드
파일만 든 시간 폴더를 만듭니다. 그 폴더가 가장 최근이면 `startFrom latestTime`은 `p`가 없어
멈춥니다.

솔버가 모드 파일을 `runTime.write()` 밖에서 쓰므로 `purgeWrite`는 이 폴더들을 세지 않습니다. 이
내용은 코드를 읽고 얻은 것이며, 실행으로 시험하지는 않았습니다.

이 검증은 PODFoam만 다룹니다. `PODFoam_Debug`, `APMOSFoam`, `AEFoam`도 같은 방식으로
스냅샷 배열을 소유합니다. 이 세 솔버는 버퍼를 복사하고 할당을 검사합니다. 세 솔버의 그 밖의 코드는
바뀌지 않으며, 세 솔버의 `pEqn.H`는 단순한 `pEqn.solve()`를 그대로 씁니다.

이 검사는 자료 연결이 동작하는지 보는 시험이며, 케이스의 물리적 타당성을 검증한 것은
아닙니다. 케이스에는 다음 문제가 남아 있습니다.

- `log.checkMesh`는 가로·세로 비율이 큰 셀 192개를 보고합니다.
- 비직교 각도가 70도를 넘는 면 16개도 보고합니다.
- 초기 압력 변화가 큽니다.
