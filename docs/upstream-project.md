# PythonFOAM 원본 프로젝트 안내

## OpenFOAM과 Python으로 계산 중에 자료 분석하기

PythonFOAM은 [OpenFOAM](https://www.openfoam.com) 계산 도중 Python 모듈로 자료를 분석하는 프로젝트입니다. OpenFOAM 사례 실행을 자동화하는 도구인 PyFOAM과는 다릅니다. 여기서는 OpenFOAM이 Python 함수와 클래스를 직접 호출합니다. Python의 기계학습 도구를 이용하거나 알고리즘을 빠르게 시험하는 등, 계산 작업 일부를 Python에 맡길 수 있습니다.

이 문서는 [영문 참고 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/upstream-project.md)를 옮긴 것입니다. 아래 버전·설치·디버깅·Docker 안내는 원본 작성 당시 기준입니다. 한국어판에서 명령을 새로 검증하거나 최신 환경에 맞춰 바꾸지 않았습니다. `PODFoam/validation/`과 `PODFoam/llm_demo/`는 원본 예제를 바탕으로 이 분기에서 추가한 검증·모델 연결 안내입니다.

원본에서 별도 수정 없이 컴파일할 수 있을 것으로 안내한 OpenFOAM 버전은 다음과 같습니다.

- openfoam.com 배포판: v2012, v2106
- openfoam.org 배포판: 8

ALCF PythonFOAM 워크숍의 자세한 실습은 [튜토리얼 영상](https://www.youtube.com/watch?v=-Sa2OEssru8)에서 볼 수 있습니다.

## 원본의 준비 항목

- OpenFOAM
- NumPy와 개발용 헤더 파일
- TensorFlow 2.1
- matplotlib
- python-dev-tools

## 예제 구성

1. `Solver_Examples/`

   - `PODFoam/`: `pimpleFoam`에 계산 중 시점별 자료를 모으는 기능을 넣은 예제입니다. OpenFOAM에서 Python의 Streaming-SVD 클래스 객체를 사용해, 자료가 추가될 때마다 SVD(Singular Value Decomposition, 특잇값 분해)를 갱신합니다. 이 분기의 `PODFoam/validation/`은 OpenFOAM v2106에서 연결을 확인하고, `PODFoam/llm_demo/`는 한 단계의 수치와 계산값 이미지를 로컬 시각·언어 모델에 보내는 선택적 콜백을 추가합니다. 자세한 내용은 [모델 연결 예제 안내](../Solver_Examples/PODFoam/llm_demo/README.md)를 참고하세요.
   - `APMOSFoam/`: `pimpleFoam`에서 모은 시점별 자료로 병렬 SVD를 수행합니다. 앞 예제가 하나의 프로세스에서 SVD를 계산한다면, 이 예제는 자료를 여러 프로세스에 나눠 전체 자료의 SVD를 구합니다. 다만 새 자료가 들어올 때마다 순차적으로 갱신하는 방식은 아닙니다.
   - `AEFoam/`: `pimpleFoam` 계산 중에 자료를 모아 딥러닝 오토인코더를 학습하는 예제입니다. 오토인코더는 자료를 압축한 뒤 복원하도록 학습하는 신경망입니다.

2. [`TurbulenceModel_Examples/`](../TurbulenceModel_Examples/README.md)

   원본에서 개발 중으로 표시한 난류 모델 예제입니다. 폴더 안의 안내 문서를 참고하세요.

## 원본의 컴파일·실행 절차

`prep_env.sh`에서 Python과 NumPy의 헤더·라이브러리 경로를 지정하고 OpenFOAM 8 환경을 불러오도록 설정합니다. **경로는 사용하는 Python 환경의 include/lib 위치에 맞게 바꿔야 합니다.** 각 솔버 예제의 `Run_Case/`에 있는 Python 모듈은 `numpy`, `matplotlib`, `tensorflow`를 사용하므로 해당 환경에 설치되어 있어야 합니다.

원본의 설치 안내는 `pip install tensorflow==2.1`로 TensorFlow와 필요한 NumPy를 설치하고, `pip install matplotlib`로 그림 도구를 추가하는 순서입니다. `mpi4py`는 `pip install mpi4py`로 설치하도록 안내합니다. 이 명령들은 당시 의존성 버전을 그대로 보존한 것입니다.

1. **솔버 예제:** `source prep_env.sh`를 실행한 뒤 원하는 예제 폴더(예: `PODFoam/`)로 이동해 `wclean && wmake`로 빌드합니다. 실행 사례는 `Run_Case/`에 있습니다. 이 폴더의 `python_module.py`도 확인하세요.

2. **난류 모델 예제:** [`TurbulenceModel_Examples/`의 안내](../TurbulenceModel_Examples/README.md)를 참고하세요.

## 원본의 2022년 12월 16일 추가 안내: C++ 디버깅

원본에서는 Visual Studio Code로 PythonFOAM의 C++ 부분을 디버깅하는 방법을 소개합니다. 이를 위해 디버그 모드로 빌드한 OpenFOAM-8이 필요합니다. 아래 줄 번호와 경로는 당시 예제 기준입니다.

1. OpenFOAM-8 소스를 내려받습니다.

```
git clone https://github.com/OpenFOAM/OpenFOAM-8.git
git clone https://github.com/OpenFOAM/ThirdParty-8.git
```

`OpenFOAM-8/etc/bashrc`의 84행을 다음과 같이 설정합니다.

```
export WM_COMPILE_OPTION=Debug
```

`source OpenFOAM-8/etc/bashrc`로 환경 변수를 불러옵니다. 이어서 `ThirdParty-8/`에서 `./Allwmake`를 실행하고, `OpenFOAM-8/`에서 `./Allwmake -j`를 실행합니다. 이 절차에서는 ParaView 컴파일을 건너뜁니다. 원본은 디버그용 OpenFOAM과 최적화된 OpenFOAM을 각각 빌드해 두는 방식을 권합니다.

2. Visual Studio Code를 설치하고 C/C++의 IntelliSense 및 확장 팩을 준비합니다.

3. 솔버를 빌드할 폴더로 이동합니다. 원본의 예시는 `PODFoam_Debug/`입니다. 이 폴더에는 `PODFoam_Debug`를 빌드할 파일과 `wmake` 설정이 있습니다. 디버그 실행을 위해 유체 해석 사례의 파일, 즉 `run_case/`의 내용도 같은 빌드 폴더에 둡니다.

4. `PODFoam_Debug` 안에 `.vscode/`라는 숨김 폴더를 만들고 다음 네 파일을 추가합니다.

```
launch.json
c_cpp_properties.json
tasks.json
settings.json
```

내용은 저장소의 `PODFoam_Debug/.vscode`에 있는 예제 파일을 참고합니다. 추가 설명은 [Visual Studio Code로 OpenFOAM 디버깅하기](https://github.com/Rvadrabade/Debugging-OpenFOAM-with-Visual-Studio-Code/)에 있습니다.

5. 새 터미널에서 `source prep_env.sh -debug`를 실행해 디버그용 OpenFOAM 환경을 불러옵니다. 올바른 `bashrc`를 가리키는지 확인해야 합니다. 원본의 경로는 작성자의 개인 컴퓨터 기준이므로 각 환경에 맞춰야 합니다. 앞서 설명한 절차에 따라 `PODFoam_Debug/`에서 디버그 버전의 솔버를 컴파일합니다.

6. `PODFoam_Debug/`에서 `code .`로 Visual Studio Code를 엽니다. `PODFoam_Debug.C`에 중단점을 놓고 디버그 패널에서 F5를 눌러 시작합니다. 이후에는 일반적인 gdb 사용 방식을 따릅니다.

원본 작성 당시 C++와 Python을 함께 추적하는 혼합 디버깅은 조사 중이었습니다.

## 원본의 Docker 실행 안내

원본은 저장소 내용을 담은 [Docker 이미지](https://hub.docker.com/repository/docker/romitmaulik1/pythonfoam_docker)를 안내합니다. Docker가 설치된 컴퓨터에서 다음 명령으로 PythonFOAM 환경이 들어 있는 이미지를 내려받도록 되어 있습니다.

```docker pull romitmaulik1/pythonfoam_docker:latest```

이어서 다음 명령을 사용합니다. 명령 블록은 원본 그대로입니다.

```
docker run -t -d -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --privileged --name pythonfoam_container romitmaulik1/pythonfoam_docker
xhost +local:docker # For running GUI applications from docker
docker start pythonfoam_container
docker exec -i -t pythonfoam_container /bin/bash
```

이 명령은 `pythonfoam_container`라는 컨테이너를 만들고, 안에서 작업할 셸을 엽니다. 셸에서 `/home/PythonFOAM`으로 이동하면 소스와 시험 사례를 볼 수 있습니다. Docker 사용법은 [Jean Rabault의 튜토리얼](https://github.com/jerabaul29/Cylinder2DFlowControlDRLParallel/blob/master/Docker/README_container.md)을 참고하세요.

## 원본 개발 연락처와 연구 지원

원본 프로젝트의 문의 연락처는 Romit Maulik(rmaulik@anl.gov)입니다.

이 연구에는 미국 일리노이주 Lemont의 Argonne National Laboratory에 있는 Argonne Leadership Computing Facility(ALCF)의 자원이 사용되었습니다. ALCF는 미국 에너지부 과학국(U.S. Department of Energy, Office of Science)의 사용자 시설입니다.

연구의 일부는 IIT-Chicago 컴퓨터과학과의 [SPEAR Team](http://www.cs.iit.edu/~lan/SPEAR-Team.html)에서도 수행했으며, 미국 국립과학재단(NSF) 과제 [2119294](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2119294&HistoricalAwards=false)의 지원을 받았습니다. 해당 과제의 책임연구자는 Zhiling Lan입니다.

## 라이선스

Python 연결 부분에는 [Argonne 오픈소스 라이선스](../LICENSE)가 적용됩니다. 법적 라이선스 원문은 번역하거나 변경하지 않았습니다.
