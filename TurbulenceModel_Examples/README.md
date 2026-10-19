# Python을 호출하는 난류 모델 컴파일하기

이 문서는 원본의 OpenFOAM 8용 안내를 번역한 것입니다. 경로, 명령과 줄 번호는 당시 예제 기준이며, 한국어판에서 설치·실행을 다시 검증하거나 최신 버전에 맞춰 바꾸지 않았습니다.

## 시작하기 전에

원본 안내에서는 NumPy와의 호환성을 위해 `arglist` 초기화 옵션을 `false`로 둔 별도 솔버 복사본을 사용합니다. 관련 설명은 [pybind11 이슈의 댓글](https://github.com/pybind/pybind11/issues/1889#issuecomment-1029909985)을 참고하세요.

## OpenFOAM 8에 새 RANS 난류 모델 추가하기

RANS(Reynolds-Averaged Navier–Stokes)는 레이놀즈 평균 나비에–스토크스 방정식으로, 평균 흐름을 다루는 난류 해석 방식입니다.

1. `TurbulenceModels/momentumTransportModels/RAS`에서 원하는 새 모델과 가장 비슷한 기존 모델을 복사합니다. 이 예제에서는 `kEpsilon/`을 복사해 `PykEpsilon/`로 이름을 붙였습니다. 폴더 안의 파일명과 클래스 이름도 `kEpsilon`에서 `PykEpsilon`으로 바꿉니다.

2. `PykEpsilon.C`와 `PykEpsilon.H`의 변경 내용을 확인합니다. 클래스가 생성될 때 Python을 초기화하고, 난류 모델을 계산할 때마다 Python을 호출합니다. 원본은 `PODFoam/`과 같은 사례를 사용하되, 주 솔버 대신 난류 모델 안에서 SVD(Singular Value Decomposition, 특잇값 분해)에 쓸 시점별 자료를 모으도록 구성했습니다.

3. `TurbulenceModels/incompressible/kinematicMomentumTransportModels/kinematicMomentumTransportModels.C`에 복사·수정한 모델을 추가합니다. 원본 안내의 101–102행을 참고하세요.

4. `TurbulenceModels/`에서 `compile_new_models.sh`를 실행해 새 난류 모델을 빌드하고 OpenFOAM에 등록합니다.

5. 기존 솔버(예: `simpleFoam`)에서 새 난류 모델을 사용하면 NumPy 호환 문제로 메모리 접근 오류나 부동소수점 오류가 날 수 있습니다. 이를 처리하는 솔버 복사본의 예제가 `PysimpleFoam`입니다. 원본에서는 `simpleFoam`을 복사해 이름을 바꾸고, `PysimpleFoam.C`의 44–49행을 추가했으며, `PysimpleFoam/Make/files`의 실행 파일명과 소스 파일명을 변경했습니다. `PysimpleFoam/`에서 `wclean && wmake`로 컴파일합니다.

6. `PykEpsilon` 모델을 시험하려면 `PysimpleFoam/PitzDaily` 사례로 이동해 `PysimpleFoam`으로 실행합니다. `constant/momentumTransport`에는 새 난류 모델이, `system/controlDict`에는 새 솔버가 지정되어 있습니다.

이 절차는 난류 모델 안에서 Python과 OpenFOAM을 연결하는 예제입니다. 원본은 이를 데이터 기반 난류 모델링에 활용하는 출발점으로 제시합니다. 문의는 [원본 프로젝트 안내](../docs/upstream-project.md)의 연락처를 참고하세요.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/TurbulenceModel_Examples/README.md)
