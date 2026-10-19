# linalgFoam: 행렬과 해를 Python으로 보내는 예제

이 솔버는 `laplacianFoam`을 변형한 예제입니다. OpenFOAM에서 만든 강성 행렬, 외력 벡터, 계산한 해를 C++ 배열에 넣은 뒤 NumPy 배열로 Python에 전달합니다. 이를 통해 NumPy, PETSc 등 여러 풀이 도구를 비교할 수 있습니다.

OpenFOAM은 효율을 위해 전체 행렬을 그대로 저장하지 않습니다. 이 예제에서는 OpenFOAM의 LDU(Lower-Diagonal-Upper, 하삼각·대각·상삼각) 저장 방식과 셀 사이의 연결 정보를 이용해 행렬과 벡터를 구성합니다.

## 원본 예제의 코드 변경 내용

아래 줄 번호는 원본 문서 작성 당시 기준입니다. 이 한국어 문서는 기존 예제를 설명하며, 새 실행 결과를 추가한 것은 아닙니다.

- 65–84행: Python과 NumPy를 초기화하고, `Python_Module`과 필요한 함수를 불러옵니다.
- 86–91행: 함수 인수를 전달할 튜플을 만듭니다.
- 124–131행: 셀 면의 연결 정보와 하삼각·상삼각·대각 성분을 `scalarField` 객체로 가져옵니다.
- 137–161행: 셀 면의 연결 정보에 따라 하삼각·상삼각·대각 성분을 `simpleMatrix` 객체에 넣습니다.
- 163–176행: 경계조건에 따른 항을 더합니다.
- 183–192행: 만든 강성 행렬과 외력 벡터를 C++ 배열에 넣습니다. 이후 NumPy 배열로 바꾸어 Python에 전달합니다.
- 199–202행: 해 벡터를 C++ 배열에 넣습니다. 이후 NumPy 배열로 바꾸어 Python에 전달합니다.

## 원본에 제시된 잔차 그림

Python에서 얻는 잔차 그래프의 예시는 다음과 같습니다. 잔차는 계산한 해를 방정식에 넣었을 때 남는 차이를 뜻합니다.

![원본 예제의 잔차 그래프](https://github.com/SumedhSCU/PythonFOAM/assets/143654947/f0e4269e-4aa8-4614-a900-858695a6262c)

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/linalgFoam/README.md)
