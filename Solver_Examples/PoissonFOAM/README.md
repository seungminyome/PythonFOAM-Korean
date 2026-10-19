# PoissonFOAM

이 예제는 Argonne National Laboratory의 ALCF 연구 보조원 Deepinder Jot Singh Aulakh가 구현한 FV-PINN입니다. FV는 유한체적법(Finite Volume), PINN은 물리 정보를 반영하는 신경망(Physics-Informed Neural Network)을 뜻합니다. 방법에 관한 설명은 [관련 논문](https://doi.org/10.1063/5.0097480)을 참고하세요.

OpenFOAM이 포아송 방정식의 계수 행렬 `A`를 Python에 전달하면, Python 쪽에서 TensorFlow 기반 최적화 도구가 `AX = B`를 만족하는 해 `X`를 구합니다. PythonFOAM에서 연립일차방정식 풀이를 Python 쪽에 맡길 수 있음을 보여 주는 기본 예제입니다.

이 설명은 기존 예제의 영문 안내를 옮긴 것입니다. 한국어판을 만들며 이 예제를 새로 실행하거나 성능을 검증하지는 않았습니다.

[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/Solver_Examples/PoissonFOAM/README.md)
