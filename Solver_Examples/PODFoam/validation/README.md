# OpenFOAM v2106에서 PODFoam의 C++·Python 연결 검증

20,540개 셀로 구성된 PODFoam 사례를 직렬로 10단계 실행해 C++와 Python 사이의 자료 왕복 전달을 확인합니다. 각 스냅샷이 독립된 배열로 Python에 도착하는지, NumPy가 속도 성분마다 SVD 모드 5개를 반환하는지, 그 모드가 OpenFOAM 필드로 돌아오는지, 솔버가 정상 종료하는지를 검사합니다. `Run_Case` 자체는 바꾸지 않고 복사본에서 실행합니다.

POD는 Proper Orthogonal Decomposition(적합직교분해), SVD는 Singular Value Decomposition(특이값 분해)을 뜻합니다. 여기서 모드는 스냅샷 자료에서 찾은 대표적인 공간 패턴입니다.

```bash
cd Solver_Examples/PODFoam
./validation/run_v2106.sh                      # new directory ../../../pod-v2106.XXXXXX
./validation/run_v2106.sh --resume <run-dir>   # reuse mesh and reference solver output
```

환경 변수는 `OPENFOAM_BASHRC`(기본값 `/usr/lib/openfoam/openfoam2106/etc/bashrc`), `PYTHON`(기본값 `/usr/bin/python3`, numpy 필요), `POD_WORKSPACE`(기본값은 저장소 작업 폴더의 상위 폴더)입니다. 실행 파일은 해당 실행 폴더의 `bin/`에 빌드하므로 `FOAM_USER_APPBIN`을 바꾸지 않습니다.

## 스크립트가 하는 일

1. 함께 제공된 원래 사례를 표준 `pimpleFoam`으로 실행해, 기존 설정에서 확인된 발산을 재현합니다. 설정은 `deltaT=1e-5`와 LES(Large Eddy Simulation, 대와류 모사)이며, 최대 Courant(쿠랑) 수는 약 21이고 두 번째 단계에 NaN(숫자로 표현할 수 없는 값)이 나타납니다. `checkMesh`는 가로·세로 비율이 큰 셀 192개와 비직교 각도가 70도를 넘는 면 16개를 보고합니다. 이 복사본의 이름은 `baseline-pimple`이며, 부동소수점 오류 감지 기능을 끄고 실행합니다.
2. 짧은 시험에서 발산하지 않도록 설정한 복사본 `fixed-pimple`을 준비하고 `pimpleFoam`으로 실행합니다. 층류, 초기 U = (32.2 0 0), `deltaT=1e-7`, Euler 시간 적분, 상류 차분 대류항, 제한된 비직교 보정, 압력 풀이의 `DICGaussSeidel` 완화기를 사용합니다.
3. 같은 사례의 다른 복사본에 이 폴더의 `python_module.py`를 넣어 `fixed-pod`를 준비합니다. 다시 빌드한 PODFoam을 `podSvdInterval 10`으로 10단계 실행하고 `fixed-pimple`과 비교합니다.

사례 설정 변경은 `prepare_case.py`에 있습니다. `python_module.py`는 연결 확인에 필요한 최소 모듈입니다. 스냅샷 10개와 성분별 모드 5개를 다루며, 검사를 위해 `python_svd_audit.npz`에 저장합니다.

## 통과 기준 — `verify.py`

- 두 솔버 모두: 1e-7 ... 1e-6초에 해당하는 `Time =` 기록이 정확히 10개이고, `End`로 끝나며 `FOAM FATAL`이 없어야 합니다. 모든 잔차와 저장 필드가 유한한 값이어야 하고, 선형 방정식 풀이가 반복 상한인 1000회에 도달하지 않아야 하며, 최대 Courant 수는 1보다 작아야 합니다.
- PODFoam 로그: `POD snapshot accepted` 기록 10개, `POD SVD returned to OpenFOAM: rows=61620 modes=5 finite=true` 기록 1개, `Python finalized successfully` 기록이 있어야 합니다.
- Python이 보관한 스냅샷은 저장된 U 필드와 상대 허용 오차 rtol 1e-10 안에서 같아야 합니다. 반환된 모드는 서로 직교하고 각각 길이가 1이어야 하며, 스냅샷 행렬에서 계산한 고유값 관계를 만족해야 합니다. 저장된 `upod_*`, `vpod_*`, `wpod_*` 필드와도 같아야 합니다.
- `fixed-pod`의 U와 p는 모든 단계에서 `fixed-pimple`과 같아야 합니다. 상대 허용 오차는 rtol 1e-10, 절대 허용 오차는 atol 1e-9입니다.

모든 검사를 통과해야 `PASS`를 출력합니다. 통과한 실행 `pod-v2106.c5jpOq`(2026-10-10)에서는 최대 Courant 수 0.211, 스냅샷 최대 오차 5e-11, 모드 최대 오차 5e-13을 기록했고, 필드 파일 45개를 확인했습니다.

## 연결을 위해 수정한 솔버 부분

관련 파일은 `PODFoam.C`, `PythonCreate.H`, `PythonComm.H`, `pEqn.H`입니다.

- v2106의 인자 처리 방식인 `setRootCaseLists.H`를 사용합니다. NumPy C API(Application Programming Interface, 응용 프로그램 인터페이스)를 불러올 때 오류를 확인하고, `-case`가 동작하도록 사례 폴더를 `sys.path`에 넣습니다.
- 스냅샷을 Python이 소유하는 NumPy 배열에 복사합니다. `PyArray_SimpleNewFromData`로 솔버 메모리를 직접 보는 방식은 사용하지 않습니다. 호출 전에 U와 p가 유한한 값인지 확인합니다.
- 반환값이 시스템의 기본 바이트 순서를 쓰는 float64 ndarray인지, 모양이 `(3*cells, min(truncation, snapshots))`인지, 값이 유한한지 검사합니다. 결과는 `zeroGradient` 필드로 저장합니다.
- `pEqn.solve()`는 v2106의 `pimpleFoam`과 같이 마지막 보정에서 `pFinal` 솔버를 사용합니다. 이를 적용하지 않으면 POD 솔버의 결과가 기준 실행과 달라집니다.
- Python 초기화·호출·종료 구간을 `sigFpe::ignore`로 감쌉니다. NumPy는 불러오는 과정에서 컴퓨터의 수치 한계를 알아보려고 의도적으로 오버플로를 일으킵니다. 이를 구분하지 않으면 OpenFOAM의 FPE(Floating Point Exception, 부동소수점 예외) 감지 기능이 솔버 발산으로 보고합니다.
- 끝에서는 함수 객체를 먼저 해제한 뒤 `Py_FinalizeEx()`를 호출합니다.
- `controlDict`의 선택 항목으로 `podSvdInterval`을 추가했습니다. 0이면 원래처럼 결과를 저장하는 시점에 SVD를 실행합니다.

이 검사는 자료 연결이 동작하는지 확인하는 시험입니다. 사례의 물리적 타당성을 검증한 것은 아닙니다. 격자 품질 문제와 초기의 큰 압력 변화는 여전히 남아 있습니다.

[영문 원문](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/PODFoam/validation/README.md)
