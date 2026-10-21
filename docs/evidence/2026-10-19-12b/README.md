# 10월 19일 근거, GPU 노드의 Gemma 4 12B

10월 17일 쌍별 재생을 다시 보낸 기록입니다. 이번에는 MedicineBow 클러스터(와이오밍 대학교)의
NVIDIA A30 한 장에서 Gemma 4 12B QAT Q4_0에 보냈습니다. Slurm 작업 24696203, 코드
`934da23`(영문 저장소, 이 저장소에서 같은 코드는 `f4a99f3`). 요청을 만들고 채점하는 코드는
`23089bb`와 바이트 단위로 같습니다. 솔버는 돌리지 않았습니다.

[10월 17일 보고서](../../results.md#gpu에서-gemma-4-12b로-같은-재생-2026-10-19) ·
[같은 요청의 E2B 기록](../2026-10-17/README.md) ·
[영문 문서](https://github.com/seungminyome/PythonFOAM/blob/main/docs/evidence/2026-10-19-12b/README.md)

## 파일

| 파일 | 담긴 내용 |
|---|---|
| [ablation/](ablation/) | 요청 6개, 받은 원문과 파싱한 답, 결과와 측정값, 실행기의 [manifest](ablation/manifest.json)와 [요약](ablation/summary.json), 작업이 복사해 넣은 GPU 이름·모델 목록·런타임 manifest |
| [answer-review.json](answer-review.json) | 답 여섯 개를 사람이 따로 검토한 기록. 자동 측정값과 별개 |
| [job/replay_12b.slurm](job/replay_12b.slurm) | 실제로 돌린 작업 스크립트(클러스터 설정 줄 포함) |
| [job/pod-12b-replay-24696203.out](job/pod-12b-replay-24696203.out) | 작업 출력 |
| [job/sacct.txt](job/sacct.txt) | GPU 확인 작업(24695930), 빌드 작업들과 재생 작업의 Slurm 사용 기록 |
| [runtime/server-20261019T090809Z.txt](runtime/server-20261019T090809Z.txt) | llama-server 로그 |
| [runtime/build-24696057.txt](runtime/build-24696057.txt), [runtime/build_llama.sbatch](runtime/build_llama.sbatch) | llama.cpp b11429를 소스에서 CUDA로 빌드한 기록과 그 작업 스크립트 |
| [runtime/build-24695932.txt](runtime/build-24695932.txt), [runtime/build_llama-24695932.sacct-B.txt](runtime/build_llama-24695932.sacct-B.txt) | CPU 노드에서 실패한 첫 빌드와 그 작업 스크립트 |
| [runtime/sha256.txt](runtime/sha256.txt) | 가중치, 프로젝터, 미리 빌드된 llama.cpp 압축 파일(쓰지 않음)의 해시 |
| [manifest.json](manifest.json) | 파일 출처, 크기, 해시 |

## 설정

- 요청 본문 6개는 10월 17일 것에서 `model`만 바꿨습니다
  (`gemma-4-12b-it-qat-q4_0-vision`). 질문, 수치, PNG(`05a876ff…`)가 같고, 시드 20261017~20261019,
  순서 A1 B1 B2 A2 A3 B3.
- Gemma 4 12B QAT Q4_0(매개변수 11,907,350,576개, GGUF 6,975,879,296바이트)과 그 이미지
  프로젝터. 출처 `google/gemma-4-12B-it-qat-q4_0-gguf`.
- llama.cpp b11429(커밋 `d812350`, E2B와 같음)를 GCC 14.2.0과 CUDA 12.8로 소스에서 빌드. 모든
  층을 GPU에, 문맥 2048, 슬롯 1, reasoning 끔. `--ubatch-size`가 128이라서 서버가 이미지 토큰
  상한을 256에서 128로 낮췄습니다. 그림이 더한 프롬프트 토큰은 106개로 E2B와 같았습니다.
- 작업이 서버를 직접 띄웠으므로 첫 요청은 빈 프롬프트 캐시(`cache_n` 0)에서 시작했습니다. 모델
  로드에 2.7 s, 서버가 응답하기 시작했을 때 GPU 메모리 24576 MiB 중 7713 MiB를 쓰고 있었습니다.

## 결과

| | E2B, CPU, 2026-10-17 | 12B, A30, 2026-10-19 |
|---|---:|---:|
| 수치만: 답한 위치 | (0.6012, 0.1143) m, 3번 중 3번 | 없음, 3번 모두 "unknown" |
| 수치만: 정답 셀과의 거리 | 60.92 cm | 채점 안 됨 |
| 수치 + 그림: 답한 위치 | (0.5, 0.1143) m, 3번 중 3번 | 없음, 3번 모두 "unknown" |
| 수치 + 그림: 정답 셀과의 거리 | 50.97 cm | 채점 안 됨 |
| 요청당 시간, 수치만 | 14.5~55.6 s | 2.0~3.3 s |
| 요청당 시간, 수치 + 그림 | 13.2~20.8 s | 2.1~2.7 s |
| 빈 캐시에서의 첫 프롬프트 | 1461토큰에 41.3 s | 1466토큰에 1.6 s |
| 생성 속도 | 초당 8.5~8.9토큰 | 초당 62.3~62.8토큰 |
| 답 하나의 단어 수(요청은 45단어 미만) | 28~34 | 52~54 |

두 모델 모두 최대 속력의 위치를 찾지 못했습니다. E2B는 매번 틀린 위치를 댔고, 12B는 위치를 대지
않았습니다. 위치를 대지 않은 것은 오차 0이 아닙니다. 12B의 답은 모두 입력에 있던 최대 속력
(82.5275 또는 82.53 m/s)을 맞게 옮겼습니다. 그림 포함 답 셋은 가능한 해석으로 빠른 흐름이
"concentrated near x=0.00 m"라고 덧붙였습니다. 정답 x는 0.000538 m이지만 y가 없고, 같은 답이
정확한 좌표는 주어지지 않았다고 말하며, 채점기는 `observations`만 읽으므로 이것은 세지 않았습니다.
수치만 받은 답 두 개는 그림을 보내지 않았는데도 "the image" 탓을 했고, 같은 두 답은 Ux의 SVD 에너지
비율을 흐름 방향으로 읽었습니다. 자동 검사기는 아무것도 잡지 못했습니다.
[answer-review.json](answer-review.json)에 이 점들을 답 원문과 함께 적었습니다.

시간 차이에는 더 큰 모델, CPU 대신 GPU, 이미 떠 있던 상주 서버 대신 새로 띄운 서버가 섞여 있어서 어느 하나도
떼어 내지 못합니다.

## 참고

- clone은 `934da23`이었고 `replay_12b.slurm`의 클러스터 설정 네 줄(계정, 파티션, module, PATH의
  Python)을 고친 채 커밋하지 않았습니다. [job/replay_12b.slurm](job/replay_12b.slurm)이 실제로 돌린
  파일입니다.
- 미리 빌드된 b11429 CUDA 라이브러리는 GLIBC_2.38이 필요한데 MedicineBow는 2.34라서 llama.cpp를
  소스에서 빌드했습니다. 첫 빌드(작업 24695932, CPU 노드)는 마지막 링크에서 `libcuda.so.1`을 찾지
  못해 실패했고, 두 번째(작업 24696057, A30 노드, `LDFLAGS`에 CUDA stub 라이브러리)는 6분 22초에
  성공했습니다. 두 변경 중 어느 쪽이 링크를 고쳤는지는 따로 확인하지 않았습니다. 그보다 앞선
  `srun`(작업 24695931)은 스크립트가 로그인 노드의 `/tmp` 폴더에 있어서 실패했습니다.
- [runtime/sha256.txt](runtime/sha256.txt)와
  [ablation/runtime_manifest_12b.json](ablation/runtime_manifest_12b.json)에는 내려받기만 하고 쓰지 않은
  미리 빌드된 llama.cpp 압축 파일의 해시도 들어 있습니다. runtime_manifest_12b.json의 `server_version`이
  소스 빌드를 가리킵니다. 빌드한
  실행 파일 자체의 해시는 실행 당시 남기지 않았습니다.
- 솔버를 돌리지 않았으므로 콜백 시간은 없습니다. [ablation/manifest.json](ablation/manifest.json)의
  78.255546163 s는 10월 17일 E2B 값이고 `recorded_not_new`로 표시되어 있습니다.
- 이 작업에서는 단위 테스트를 돌리지 않았습니다.
- 이 폴더에 없는 것: 가중치, 프로젝터, llama.cpp 압축 파일과 실행 파일, 그리고 작업이 만든
  tar.gz(안의 파일 44개는 [ablation/](ablation/)과 같음).
