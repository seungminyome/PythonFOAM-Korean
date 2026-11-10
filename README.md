# PythonFOAM: 비전-언어 모델로 OpenFOAM 계산 관찰하기

[![tests](https://github.com/seungminyome/PythonFOAM-Korean/actions/workflows/tests.yml/badge.svg)](https://github.com/seungminyome/PythonFOAM-Korean/actions/workflows/tests.yml)
[![evidence](https://github.com/seungminyome/PythonFOAM-Korean/actions/workflows/evidence.yml/badge.svg)](https://github.com/seungminyome/PythonFOAM-Korean/actions/workflows/evidence.yml)
![OpenFOAM v2012 | v2106 | v2212 | 8](https://img.shields.io/badge/OpenFOAM-v2012%20%7C%20v2106%20%7C%20v2212%20%7C%208-lightgrey)
![Python 3.10 | 3.12](https://img.shields.io/badge/python-3.10%20%7C%203.12-lightgrey)
[![license](https://img.shields.io/badge/license-Argonne%20OSS-blue.svg)](LICENSE)

[결과 페이지](https://seungminyome.github.io/PythonFOAM-Korean/) · [최신 보고서](docs/results-20261103.md) · [실행 방법](Solver_Examples/PODFoam/llm_demo/README.md) · [GPU 노드](Solver_Examples/PODFoam/llm_demo/hpc/README.md) · [English](https://github.com/seungminyome/PythonFOAM)

OpenFOAM이 도는 동안 Python이 유동을 이미지로 그리고, 같은 컴퓨터에서 도는 이미지 읽는
모델에게 무엇이 보이는지 묻습니다. 이 저장소는 그런 모델이 솔버 이미지에서 무엇을 읽을 수
있고 무엇을 읽지 못하는지 보여 줍니다.
[PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)의 PODFoam 예제 위에 만들었고, 모델은
[llama.cpp](https://github.com/ggml-org/llama.cpp)로 돌리며, 모델이 한 말은 솔버로 돌아가지
않습니다.

## 알아낸 것

모델은 따로 적지 않으면 Gemma 4 12B입니다. 모델은 아래 두 장, 한 시간 단계의 |U|와 p 이미지와
질문 하나를 받습니다.

| 질문 | 어떻게 됐나 | 판정 |
|---|---|---|
| 어디가 가장 빠르고, 어디가 압력이 가장 낮은가? | 대부분의 이미지에서 맞는 자리를 짚습니다. 늘 같은 자리를 찍는 것보다 훨씬 자주 맞힙니다. | 됨 |
| 이미지 방식이 중요한가? | 그렇습니다. 이미지 한 장에 필드 하나를 그리고 축을 백분율로 적으면 모델들이 48장 중 45\~48장에서 가장 빠른 유동과 가장 낮은 압력을 둘 다 맞혔습니다. 솔버의 원래 두 패널 이미지로는 2\~17장이었습니다. | 매우 중요 |
| 솔버가 도는 동안에도 되나? | 됩니다. 250단계마다 요청하면 계산 시간이 모델에 요청을 보내지 않은 같은 실행보다 1 % 미만 늘어납니다. 솔버는 두 실행에서 같은 파일을 썼습니다. | 됨 |
| 스냅샷 사이에 유동이 빨라지나, 느려지나? | 최대 속도 변화가 2 % 이상이면 읽습니다. 더 작은 변화는 대부분 잘못 읽습니다. | 뚜렷한 변화만 됨 |
| 이 계산이 곧 터지나? | 경고는 길어야 터지기 다섯 단계 전에 나옵니다. 숫자로 만든 간단한 규칙이 그만큼 또는 그보다 잘 맞힙니다. | 안 됨 |
| 이 계산은 설정이 잘못됐나? | 첫 시험에서 Gemma 4 31B가 간단한 규칙을 앞선 것은 실행 두 개 때문이었습니다. 실행 29쌍으로 더 엄격하게 한 두 번째 시험에서는 간단한 규칙보다 나은 점이 보이지 않습니다. 31B는 잘못된 실행을 더 많이 잡지만 정상 실행도 잘못됐다고 합니다. | 보이지 않음 |
| 큰 모델이 더 나은가? | 작은 E2B는 이 이미지를 제대로 읽지 못합니다. 위치는 12B로 충분합니다. 31B는 작은 압력 점을 더 잘 보지만, 설정 판단은 간단한 규칙보다 낫지 않습니다. | 부분적으로 |

정확한 수와 시험마다의 기준선은 [결과 페이지](https://seungminyome.github.io/PythonFOAM-Korean/)와
아래 보고서에 있습니다. [근거 자료 폴더](docs/evidence/README.md)에는 원래 답 전부와 해시
매니페스트가 있습니다.

<img src="docs/evidence/2026-10-22-live-v2/suite/async-describe/llm_observation/step-000250/U.png" width="415" alt="t = 0.10125 s의 |U|, 표시 영역은 x 0에서 0.12 m까지, y 0에서 0.04 m까지: 계단 뒤에 늘어선 와류"> <img src="docs/evidence/2026-10-22-live-v2/suite/async-describe/llm_observation/step-000250/p.png" width="415" alt="같은 시점의 p: y의 약 20에서 30 % 사이에 있는 저압 와류 중심">

*모델이 보는 것: 발달한 후향 계단 유동의 250단계에서 실행 중인 솔버가 그려 Gemma 4 12B에
보낸 |U|와 p입니다.*

모든 시험은 2차원 층류와 압출한 3차원 케이스 하나로 했으므로, 다른 유동에서는 다르게 읽힐 수
있습니다. 채점한 것은 위치와 정해진 단어뿐이며, 자유로운 설명
글은 채점하지 않았습니다.

## 동작 방식

솔버는 시간 단계마다 Python 훅인 `python_module.py`의 `analysis_func`를 한 번 부릅니다. 아래 그림은
비동기 모드, 곧 `LLM_ASYNC=1`에서 요청 하나가 처리되는 순서입니다. 위에서 아래로 시간 순서이고, 실선은 보내는 것,
점선은 돌아오는 것입니다. 솔버는 3번에서 바로 다음 시간 단계를 계산하고, 모델의 답을 기다리지 않습니다.

```mermaid
%%{init: {"sequence": {"mirrorActors": false}}}%%
sequenceDiagram
    autonumber
    participant S as 솔버 (PODFoam, C++)
    participant P as Python 훅
    participant W as 작업자 (fork로 만든 사본)
    participant L as 모델 서버 (llama-server)
    S->>P: 요청 단계의 상태
    P->>W: 작업자를 fork
    P-->>S: 바로 반환, 솔버는 계속 계산
    W->>L: 이미지와 요청
    L-->>W: 답
    W-->>P: 답, 나중 단계에서 읽음
```

작업자는 |U|와 p 이미지를 그려 llama.cpp의 HTTP 서버인 llama-server에 보냅니다. 답은 이미지의 바탕이 된 배열과 함께
기록합니다. 기본값인 동기 모드에서는 솔버가 답을 기다리며, 기본 마감 시간은 120초입니다.

요청은 한 번 또는 N단계마다 보내며, 답을 기다리는 요청은 한 번에 최대 8개입니다. MPI 실행은 필드를 주 rank로 모으고,
3차원 격자는 평면 단면으로 그립니다. 요청 모드 셋, 이미지 방식 둘, 모든 설정은
[llm_demo/README.md](Solver_Examples/PODFoam/llm_demo/README.md)에 있습니다.

## 빠른 시작

단위 테스트와 근거 자료 해시 확인에는 OpenFOAM도 모델도 필요 없습니다:

```bash
pip install -r Solver_Examples/PODFoam/llm_demo/requirements.txt
make test          # 테스트 177개, 2분쯤
make evidence      # 매니페스트의 파일마다 해시가 맞는지
```

OpenFOAM(v2012, v2106, v2212, 8)을 source하고 Python 3.10\~3.12가 있으면, CPU에서 작은
Gemma 4 E2B 모델로 케이스 다섯 개 묶음을 돌려 연결과 검증을 확인합니다. 내려받는 것은 모델,
이미지 프로젝터, llama.cpp로 3.4 GB쯤이고 토큰은 필요 없습니다:

```bash
export PYTHON=${PYTHON:-$(command -v python3)}   # 또는 다른 Python의 경로
export PATH=$(dirname "$PYTHON"):$PATH
export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH   # 시스템 Python이 아니면
cd Solver_Examples/PODFoam
./validation/run.sh              # C++와 Python 연결을 확인; 그 실행이 묶음의 참조 실행
./llm_demo/setup_runtime.sh      # Gemma 4 E2B Q4_0, 이미지 프로젝터, llama.cpp b11429
python3 llm_demo/runtime.py start
./llm_demo/run_demo.sh           # PODFoam 빌드, 케이스 다섯 개 실행, 검증
python3 llm_demo/runtime.py stop
```

보고서의 GPU 실행은 Slurm 노드에서 Gemma 4 12B부터 31B까지를 돌린 것이며,
[llm_demo/hpc/README.md](Solver_Examples/PODFoam/llm_demo/hpc/README.md)에 있습니다.

## 보고서

보고서마다 실행 조건, 하드웨어, 코드 리비전, Slurm 작업을 적었습니다.

- [11월 3일](docs/results-20261103.md): 잘못된 설정 시험 2. 실행 29쌍을 같은 이미지를 보는
  규칙과 비교.
- [11월 2일](docs/results-20261102.md): 네 OpenFOAM 버전의 PR 브랜치, OpenFOAM 8이 다른 까닭,
  3차원 단면 이미지, 시점 없는 불안정 시험.
- [10월 30일](docs/results-20261030.md): OpenFOAM 버전, 원본 PODFoam, 첫 잘못된 설정 시험.
- [10월 28일](docs/results-20261028.md): 동시 요청 두 개, 3차원 단면, 불안정 시험.
- [근거 자료 목록](docs/evidence/README.md) · [변경 기록](CHANGELOG.md).

## 코드 위치

관찰 기능은 `Solver_Examples/PODFoam/`의 `Python*.H` 훅과 `llm_demo/`에 있습니다. 다른 예제는
argonne-lcf/PythonFOAM과 같습니다. 브랜치 `pr/podfoam-fix`는 PODFoam 수정만 담고, `pr/podfoam-observer`는
훅과 관찰 기능을 더합니다. 그 수정이 무엇인지는 [11월 2일 보고서](docs/results-20261102.md)에 있습니다. 훅 둘은 [HOOKS.md](Solver_Examples/PODFoam/HOOKS.md)에, 연결 검증은
[validation README](Solver_Examples/PODFoam/validation/README.md)에 있습니다.

## 인용

관찰 기능을 사용한다면 PythonFOAM과 영문 저장소를 인용해 주십시오.

```bibtex
@article{maulik2022pythonfoam,
  title   = {PythonFOAM: In-situ data analyses with OpenFOAM and Python},
  author  = {Maulik, Romit and Fytanidis, Dimitrios K. and Lusch, Bethany and
             Vishwanath, Venkatram and Patel, Saumil},
  journal = {Journal of Computational Science},
  volume  = {62},
  pages   = {101750},
  year    = {2022},
  doi     = {10.1016/j.jocs.2022.101750}
}

@software{yome2026observer,
  author = {Yome, Seungmin},
  title  = {PythonFOAM: a vision-language observer for OpenFOAM runs},
  year   = {2026},
  url    = {https://github.com/seungminyome/PythonFOAM}
}
```

## 감사의 글

이 저장소는 Argonne National Laboratory의 [PythonFOAM](https://github.com/argonne-lcf/PythonFOAM)에 있는 PODFoam 예제를 확장합니다.
원본 소개와 설치 안내는 [프로젝트 참고 문서](docs/upstream-project.md)에 있습니다.
모델은 [llama.cpp](https://github.com/ggml-org/llama.cpp)로 실행합니다.
모델 가중치는 이 저장소에 포함되지 않으며, 각 모델의 라이선스를 따릅니다.
보고서의 GPU 노드 실행과 CPU 노드 실행에는 University of Wyoming Advanced Research Computing Center의 MedicineBow 클러스터를 사용했습니다.

## 라이선스

UChicago Argonne, LLC의 PythonFOAM 오픈 소스 [라이선스](LICENSE)를 그대로 적용합니다.
