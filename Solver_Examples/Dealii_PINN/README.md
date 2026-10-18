# Deal.ii와 PINN을 연결하는 예제

이 예제는 Deal.ii의 유한요소법(FEM, Finite Element Method) 코드와 물리 정보를 반영하는 신경망(PINN, Physics-Informed Neural Network)을 연결합니다. Deal.ii 코드는 한 변의 길이가 1인 정사각형에서 포아송 방정식을 풉니다. 외력 함수는 $x^2+y^2$이며, 모든 경계에 값이 0인 디리클레 경계조건을 적용합니다.

계산한 해, 경계 자유도(DoF, Degree of Freedom) 정보, 절점 좌표를 `Python_Module`로 보냅니다. Python에서는 이 자료로 PyTorch 기반 PINN을 학습합니다. C++ 유한요소 코드는 [Deal.ii Step-4 튜토리얼](https://dealii.org/developer/doxygen/deal.II/step_4.html)을 바탕으로 합니다.

## 원본 예제의 코드 변경 내용

아래 줄 번호는 원본 문서 작성 당시 기준입니다. 이 한국어 문서는 기존 예제를 설명하며, 새 실행 결과를 추가한 것은 아닙니다.

- `assemble_system()`의 238–248행: 절점 좌표를 두 `Dealii::Vector` 객체인 `coordinatex`, `coordinatey`에 넣습니다. 순서는 전체 자유도 인덱스를 따릅니다.
- `output_results()`의 305–320행: Python으로 보낼 절점 좌표를 C++ 배열에 넣습니다.
- `output_results()`의 324–332행: Python으로 보낼 경계 자유도 인덱스를 C++ 배열에 넣습니다.
- `output_results()`의 335–353행: 코드 안에서 Python과 NumPy를 초기화하고, `Python_Module`과 그 안의 함수를 불러옵니다.
- `output_results()`의 355–359행: Python으로 보낼 해를 C++ 배열에 넣습니다.
- `output_results()`의 361–388행: 경계 자유도 자료, 절점 좌표, 해 벡터를 `Python_Module`의 `run_training` 함수에 전달합니다.

## 원본에 제시된 출력 그림

![원본 예제의 PINN 출력](https://github.com/SumedhSCU/PythonFOAM/assets/143654947/2ea74a14-bff0-4f8c-bb39-b2f32e10a7ad)

원본에서는 격자점 수가 적어 matplotlib의 등고선 그림이 매끄럽지 않다고 설명합니다. 격자를 더 촘촘하게 만들고 그에 맞춰 `Python_Module`의 신경망 설정을 조정하면 개선할 수 있다는 안내입니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/pod-insitu-llm/Solver_Examples/Dealii_PINN/README.md)
