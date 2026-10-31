# PODFoam의 C++·Python 연결 검증

20,540개 셀로 구성된 PODFoam 사례를 직렬로 10단계 실행해 C++와 Python 사이의 자료 왕복 전달을 확인합니다. 각 스냅샷이 독립된 배열로 Python에 도착하는지, NumPy가 속도 성분마다 SVD 모드 5개를 반환하는지, 그 모드가 OpenFOAM 필드로 돌아오는지, 솔버가 정상 종료하는지를 검사합니다. `Run_Case` 자체는 바꾸지 않고 복사본에서 실행합니다.

```bash
cd Solver_Examples/PODFoam
./validation/run_v2106.sh                      # new directory ../../../pod-v2106.XXXXXX
./validation/run_v2106.sh --resume <run-dir>   # reuse mesh and reference solver output
```

스크립트 이름과 상관없이 OpenFOAM v2012, v2106, v2212(openfoam.com)와 OpenFOAM 8(openfoam.org)을 지원합니다. 이미 source한 OpenFOAM이 있으면 그 버전과 bashrc를 쓰고, 없으면 v2106을 씁니다. 다른 버전을 고르려면 `OPENFOAM_BASHRC`에 그 설치의 bashrc를, `POD_OPENFOAM_VERSION`에 그 설치가 알리는 버전(`WM_PROJECT_VERSION`)을 지정합니다. 둘이 다르면 스크립트가 멈추고, 실행 폴더 이름에는 버전이 들어갑니다.

```bash
OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212 ./validation/run_v2106.sh
OPENFOAM_BASHRC=/opt/openfoam8/etc/bashrc POD_OPENFOAM_VERSION=8 ./validation/run_v2106.sh
```

다른 환경 변수는 `PYTHON`(기본값은 `PATH`의 `python3`, numpy 필요)과 `POD_WORKSPACE`(기본값은 저장소 작업 폴더의 상위 폴더)입니다. `PYTHON`이 시스템 Python이 아니면 그 `lib` 폴더를 `LD_LIBRARY_PATH`에 넣어야 하며, 그러지 않으면 스크립트가 `Unresolved shared libraries`에서 멈춥니다. 스크립트는 `FOAM_USER_APPBIN`을 실행 폴더의 `bin/`으로 지정하므로 사용자의 애플리케이션 폴더에는 쓰지 않습니다.

검증은 네 버전 모두에서 Python 3.11로 통과했고, OpenFOAM 8에서는 원본의 Docker 이미지 `romitmaulik1/pythonfoam_docker`의 Python 3.6.9로도 통과했습니다.

## 스크립트가 하는 일

1. `baseline-pimple`을 준비합니다. 제공된 사례의 복사본에 `LESModel Smagorinsky`를 넣고 `controlDict`를 생성한 것(고정 `deltaT=1e-5`, 10단계)이며, 표준 `pimpleFoam`을 부동소수점 트랩을 끄고 실행합니다(openfoam.com에서는 `FOAM_SIGFPE=false`, openfoam.org에서는 어떤 값이든 트랩이 켜지므로 변수를 지웁니다). 결과는 기록만 합니다(`baseline-pimple/log.pimpleFoam`, `baseline-pimple/exit-status`). openfoam.com에서 이 복사본은 최대 Courant 수 약 21에 이르고 두 번째 단계에 NaN이 나타나며, OpenFOAM 8에서는 10단계를 마칩니다. `log.checkMesh`는 가로·세로 비율이 큰 셀 192개와 비직교 각도가 70도를 넘는 면 16개를 보고합니다. 제공된 `Run_Case`는 이 복사본과 다릅니다. 시간 간격을 스스로 조절하고(`maxCo 1`), openfoam.com에서 `LESModel`을 손으로 넣으면 원본 빌드와 이 코드 모두 약 90단계 안에 발산합니다.
2. 짧은 시험에서 발산하지 않도록 설정한 복사본 `fixed-pimple`을 준비하고 `pimpleFoam`으로 실행합니다. 층류, 초기 U = (32.2 0 0), `deltaT=1e-7`, Euler 시간 적분, 상류 차분 대류항, 제한된 비직교 보정, 압력 풀이의 `DICGaussSeidel` 완화기를 사용합니다.
3. 같은 사례의 다른 복사본에 이 폴더의 `python_module.py`를 넣어 `fixed-pod`를 준비합니다. 다시 빌드한 PODFoam을 `podSvdInterval 10`으로 10단계 실행하고 `fixed-pimple`과 비교합니다.

사례 설정 변경은 `prepare_case.py`에 있으며, 변경할 문장을 `Run_Case`에서 찾지 못하면 멈춥니다. `python_module.py`는 연결 확인에 필요한 최소 모듈입니다. 스냅샷 10개와 성분별 모드 5개를 다루며, 검사를 위해 `python_svd_audit.npz`에 저장합니다.

## 통과 기준 (verify.py)

- 두 솔버 모두: 1e-7 ... 1e-6초에 해당하는 `Time =` 기록이 정확히 10개이고, `End`로 끝나며 `FOAM FATAL`이 없어야 합니다. 모든 잔차와 저장 필드가 유한한 값이어야 하고, 선형 방정식 풀이가 반복 상한인 1000회에 도달하지 않아야 하며, 최대 Courant 수는 1보다 작아야 합니다.
- PODFoam 로그: `POD snapshot accepted` 기록 10개, `POD SVD returned to OpenFOAM: rows=61620 modes=5 finite=true` 기록, `Python finalized successfully` 기록이 있어야 합니다.
- Python이 보관한 스냅샷은 저장된 U 필드와 같아야 합니다(rtol 1e-10, atol 1e-9). 반환된 모드는 서로 직교하고 각각 길이가 1이어야 하며, 스냅샷 행렬에서 계산한 고유값 관계를 만족해야 합니다. 저장된 `upod_*`, `vpod_*`, `wpod_*` 필드와도 같아야 합니다.
- `fixed-pod`의 U와 p는 모든 단계에서 `fixed-pimple`과 같아야 합니다. 상대 허용 오차는 rtol 1e-10, 절대 허용 오차는 atol 1e-9입니다.

모든 검사를 통과해야 `PASS`를 출력합니다. 통과한 실행의 값은 대략 최대 Courant 수 0.211(OpenFOAM 8에서는 0.212), 스냅샷 최대 오차 5e-11, 모드 최대 오차 5e-13이고, `fixed-pod`에서 필드 파일 45개를 확인합니다.

## 원본 PODFoam과 달라지는 점

결과는 다음과 같이 달라집니다.

- **POD 모드.** 스냅샷은 Python이 소유하는 배열로 Python에 도착합니다. 원본 모듈은 스냅샷 구간의 첫 스냅샷을 C++ 버퍼의 뷰로 들고 있고 다음 스냅샷이 그 버퍼를 덮어쓰므로, 원본 빌드에서는 모든 스냅샷 행렬의 앞 두 열이 같습니다. 여기서는 첫 열이 첫 스냅샷을 담습니다. Python에서 그 덮어쓰기를 재현하면 모든 모드의 셀 값이 원본과 같습니다.
- **모드 파일.** 모드는 무차원 `zeroGradient` 필드로 씁니다. 원본의 모드 파일은 U 성분의 복사본이며 U의 차원과 경계 조건을 가집니다.
- **openfoam.com의 U와 p.** 압력 풀이는 그 버전의 `pimpleFoam`처럼 마지막 보정 전까지 `p` 솔버를, 마지막 보정에서 `pFinal`을 씁니다. 이 사례처럼 외부 보정이 하나이면, 그곳에서 단순한 `pEqn.solve()`는 모든 보정에서 `pFinal`을 고릅니다. openfoam.org의 `pimpleFoam`은 단순한 `pEqn.solve()`를 쓰고 이 코드도 그렇게 하므로, OpenFOAM 8에서 U, p, phi는 원본과 바이트까지 같습니다.

실행은 다음과 같이 멈추거나 다르게 동작할 수 있습니다.

- **부동소수점 트랩**은 `pimpleFoam`처럼 솔버에서는 켜고, Python 초기화·호출·종료 구간에서는 끕니다(`PythonCompat.H`의 `PythonFpeOff`, openfoam.com에서는 `sigFpe::ignore`). NumPy는 불러오는 과정에서 컴퓨터의 수치 한계를 알아보려고 의도적으로 오버플로를 일으키기 때문입니다. 원본의 인자 처리는 트랩을 꺼 두므로, 원본에서 오버플로를 지나 계속되는 실행이 여기서는 SIGFPE로 멈춥니다.
- **호출 검사.** 모듈을 불러오지 못하거나, 함수가 없거나, `snapshot_func`나 `svd_func`에서 오류나 `SystemExit`가 나면 솔버는 Python 트레이스백을 내고 멈춥니다. 스냅샷 전에 U와 p가 유한해야 합니다. `svd_func`는 시스템 기본 바이트 순서의 float64 ndarray를, 모양 `(3*cells, modes)`로, 모드 1\~`truncation`개, 유한한 값으로 돌려줘야 합니다. 제공된 모듈의 `online_mode = False`는 짧은 시험의 `writeInterval` 3과 6에서 이렇게 멈췄습니다. 아주 작은 음의 고유값이 `np.sqrt`에서 NaN이 되기 때문입니다.
- **병렬 실행.** 모드마다 경계 갱신이 rank 사이에서 자료를 주고받으므로, 모든 rank가 같은 수의 모드를 돌려줘야 합니다. 그렇지 않으면 실행이 이유를 밝히고 멈춥니다. 셀이 없는 rank는 다른 rank의 개수를 따릅니다.
- **Python 스레드.** `Py_FinalizeEx()`는 Python 함수 참조를 해제한 뒤 끝에서 실행됩니다. 이 호출은 데몬이 아닌 스레드를 기다리므로, 그런 스레드를 시작한 모듈은 스레드를 멈추기도 해야 하며, 그러지 않으면 솔버가 끝나지 않습니다.
- **`sys.path`.** `-case`가 사례의 모듈을 찾도록 사례 폴더가 맨 앞에 옵니다. 실행을 시작한 폴더는 그 뒤에 남습니다.
- **로그.** 단계마다 `Time =` 줄을 deltaT와 함께 출력하고, 검증이 이 줄을 읽습니다. 원본의 시간 측정 줄은 그대로 있습니다.

`controlDict`의 `podSvdInterval`은 새로 생긴 선택 항목입니다. 기본값 0에서는 `snapshot_func`와 `svd_func`를 정의한 모듈이 원래 일정을 따릅니다. 저장 단계는 마지막 SVD 뒤에 모은 스냅샷이 있으면 스냅샷을 모으는 대신 SVD를 실행합니다. 0보다 크면 모든 단계에서 스냅샷을 모으고 스냅샷 `podSvdInterval`개마다 SVD를 실행합니다. 그러면 다른 것을 저장하지 않는 단계의 SVD가 POD 필드만 든 시간 폴더를 만듭니다. 그 폴더가 가장 최근이면 `startFrom latestTime`은 `p`가 없어서 멈추고, `purgeWrite`는 이 폴더들을 지우지 않습니다.

이 내용은 PODFoam만 다룹니다. `PODFoam_Debug`와 `APMOSFoam`에도 C++ 버퍼 위에서 같은 `array[:,0].reshape(-1,1)` 줄이 있고, `AEFoam`에는 그 자리에 `np.expand_dims`가 있으며, 이들의 `pEqn.H`에는 단순한 `pEqn.solve()`가 있습니다. 코드를 읽기만 했고 실행하지는 않았습니다.

이 검사는 자료 연결이 동작하는지 확인하는 시험입니다. 사례의 물리적 타당성을 검증한 것은 아닙니다. 격자 품질 문제와 초기의 큰 압력 변화는 여전히 남아 있습니다.

[영문 원문](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/PODFoam/validation/README.md)
