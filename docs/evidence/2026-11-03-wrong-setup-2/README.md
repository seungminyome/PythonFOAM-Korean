# 11월 3일 근거: 잘못된 설정 시험 2

10월 30일의 첫 잘못된 설정 시험에는 잘못된 실행이 변경 종류마다 하나씩 다섯 개 있었고, 실행마다 서로
닮은 프레임 여덟 개를 썼습니다. 상수 기준선 말고 경쟁 상대는 최대 |U| 숫자 하나를 보는 규칙뿐이었습니다. 이 시험은 2차원
후향 계단 케이스의 pimpleFoam 실행 29쌍입니다. 쌍마다 기본 설정 하나를 무작위로 뽑았습니다. 그 설정을 그대로 돌린 것이 정상
실행이고, 항목 하나를 바꿔 돌린 것이 잘못된 실행입니다. 실행 하나가 표본 하나입니다. 영문 [계획](PLAN.md), 채점,
기준선, 요청 세트의 매니페스트는 모델에 요청을 보내기 전에 영문 저장소의 `97c3c41`과 `91544e6`에
커밋했습니다.

Gemma 4 31B의 4비트 QAT Q4_0 파일이 요청 1,044개에 답했습니다. 요청마다 한 프레임의 |U|와 p 이미지,
그리고 짧은 메모를 보냅니다. 알려 준 조건에서는 메모에 의도한 입구 속도와 점성을 적고, 알려 주지 않은
조건에서는 적지 않습니다. 조건마다 모델의 샘플링 온도 0으로 한 번, 0.7로 시드 둘로 실행마다 프레임 셋에
물었습니다. t0는 온도 0, t07a와 t07b는 온도 0.7에 시드 a와 b입니다.

정상 실행에 `consistent`, 잘못된 실행에 `inconsistent`라고 답하면 맞은 것입니다. 답한 원인까지 그 실행의
변경이면 '맞는 이유로 맞음'이고, 정상 실행의 원인은 `none`입니다. report.md가 labels라고 부르는 색 막대
숫자 기준선은 색 막대 숫자와 알려 준 설정으로 만든 로지스틱 회귀이며, 입력은 다섯 개입니다. 색 막대 숫자는
두 이미지의 색 막대 양 끝에 적힌 숫자 넷입니다. 입력 넷은 이 숫자에서 만듭니다. |U| 색 막대의 U 최대와
U 최소는 알려 준 속도로, p 색 막대의 p 최소와 p 최대는 알려 준 속도의 제곱으로 나눕니다. 다섯째 입력은 알려 준 점성의 로그값입니다. 회귀는 한 쌍씩 빼고 맞춥니다.

요약([results/report.md](results/report.md)와 [이유](#이유)의 수):

- 주 결과, 설정을 알려 줌, 온도 0, 실행의 마지막 프레임: 31B는 58개 중 44개를 맞힙니다. 가장 많이
  맞힌 기준선인 색 막대 숫자 기준선은 45개를 맞힙니다.
  둘은 실행 27개에서 다르며, 기준선이 14개, 모델이 13개를 맞힙니다. 정확한 McNemar 검정 p = 1.
  계획의 기준인 p < 0.05로 보면 "모델이 규칙보다 낫다"는 보이지 않았습니다.
- 31B는 잘못된 실행을 잡습니다. 29개 중 26개이며, 종류별로 입구 속도 8개 중 8, 점성 8개 중 8, 입구
  속도 분포 6개 중 6, 벽 7개 중 4입니다. 색 막대 숫자 기준선은 17개를 잡습니다. 벽 7개 중 7, 속도 4, 점성
  2, 속도 분포 4입니다.
- 31B는 오경보를 냅니다. 정상 실행 29개 중 11개에 `inconsistent`라고 답합니다. 이유 11개 중 9개는
  이미지에 후향 계단이 없다고 합니다. "no step geometry (white area)", "no sudden expansion or
  separation zone"입니다. 표시 영역은 계단 모서리에서 시작하므로 이 시험의 어느 이미지에도 흰 영역이
  없습니다. 같은 두 문구는 잡아낸 잘못된 실행의 이유 26개 중 4개에도 나오고, 그 26개 중 7개는 계단이
  없다고 합니다. 색 막대 숫자 기준선의 오경보는 1개입니다.
- 맞는 이유로 맞음: 58개 중 27개. `consistent`라고 답한 정상 실행 18개와 잘못된 실행 9개, 곧 속도 7과
  벽 2입니다. 점성 실행 중 원인이 `viscosity`인 답은 없고, 말한 원인은 벽 3, 기타 3, 입구 속도 1, 입구
  속도 분포 1입니다. 입구 속도 분포 실행 6개에서는 답한 원인이 모두 `inlet_speed`이고, 이유는 색 막대의 최댓값이 알려 준 속도보다
  낮다는 것입니다.
- 알려 주지 않은 조건, 곧 알려 준 숫자가 없으면 31B는 58개 중 51개에 `inconsistent`라고 답하고 28개를
  맞힙니다. 상수 기준선의 29개보다 적습니다. 알려 준 숫자도 색 막대 숫자도 읽지 않고 픽셀만 쓰는 기준선은
  44개를 맞힙니다.
- 샘플링 온도 0.7에서는 시드 두 개 각각에서 알려 준 답 58개 중 10개가 바뀌고, 맞힌 수는 둘 다 낮아집니다.
  58개 중 34개와 38개.
- 앞선 프레임인 6000, 7000단계, 알려 줌, 온도 0: 58개 중 37개와 42개 맞힘. 알려 준 온도 0 프레임 174개
  전체: 123개 맞힘.

## 작업

| 작업 | 내용 | 노드 | 시각(MST, 2026-11-03) |
|---|---|---|---|
| 25106856(배열 0\~11), 25106882(작업 12) | 예비 실행 13개 | CPU, `teton`(ttest01, ttest02) | 20:07\~20:18 |
| 25106926(배열 0\~59) | 설계의 pimpleFoam 실행 60개, 작업 하나에 실행 하나; 작업 11(B06-W)은 발산 | CPU, `teton`(ttest01\~ttest04, t286) | 20:21\~20:49 |
| 25107036 | `flow-check`, `build`, `check`, `baselines`, `contact` | CPU(ttest01) | 20:49\~20:54 |
| 25107037 | 첫 GPU 작업. 실행기가 찾는 매니페스트 키가 없어서 요청 전 42 s 만에 멈춤 | NVIDIA RTX A6000(mba6000-001) | 21:12\~21:13 |
| 25107731 | 요청 1,044개에 Gemma 4 31B(`window_test.slurm`, `PICTURE_TEST_SCRIPT=wrong_setup_test2.py`) | NVIDIA RTX A6000(mba6000-001) | 21:14\~22:26 |

시작과 끝 시각은 [job/sacct.txt](job/sacct.txt)에 있습니다. 보고서와 이유는 2026-11-04에 로그인 노드에서
`wrong_setup_test2.py report`로 만들었습니다. test-set/manifest.json 안의 메모는 더한 키의 시각을
"2026-11-03 21:20"이라고 적었습니다. 그 키를 담은 커밋 `3363525`는 21:14:12 MST이므로 메모의 시각이
틀렸습니다. 영문 저장소의 커밋은 계획이 `97c3c41`, 단위 테스트가 `33553c4`, B06 제외가 `3bc6d51`,
요청 세트의 매니페스트와 기준선이 `91544e6`, 매니페스트 키가 `3363525`입니다. 마지막 커밋은 작업 25107037
뒤, 25107731 전입니다. 작업 스크립트는 [jobs/](jobs/)에 있습니다.

## 실행

모든 실행은 OpenFOAM v2212의 층류 pimpleFoam 실행입니다. PISO와 div(phi,U)의 upwind를 쓰고, 셀 20,540개의
격자에서 돌렸습니다. 설정은 첫 시험과 같습니다. Δt는 5×10⁻⁶ s로 고정합니다. t = 0.1 s부터 t = 0.14 s까지
8,000단계를 계산해 500단계마다 저장합니다. 실행마다 10월 22일 발달한 유동의 t = 0.06\~0.1 s 사이 저장 상태
하나를 `0.1`이라는 디렉터리로 복사해 시작합니다. 기본 설정의 입구 속도는 입구 패치에, 점성은 `transportProperties`에 넣습니다. 발달한 유동
자체는 32.2 m/s와 1.56×10⁻⁵ m²/s로 돌렸습니다. 계단 모서리는 x = 0, y = 0.0127 m입니다. 표시 영역은 x 0\~0.12 m, y 0\~0.04 m입니다. 이 표시
영역에서 계단의 면은 왼쪽 가장자리의 높이 32 % 아래이고, 입구와 위쪽 벽은 표시 영역 밖입니다.

`flow-check`([flow-check.json](flow-check.json))는 실행 58개를 모두 받아들였습니다. 모두 8,000단계 뒤
`End`로 끝났고, 마지막으로 저장한 U와 `transportProperties`에 설계의 항목이 있습니다. 실행 전체의 가장
큰 Courant 수는 정상 실행 21개와 잘못된 실행 24개에서 1을 넘습니다. 그중 44개는 최댓값이 2\~41단계에
있습니다. 시작 상태는 32.2 m/s의 발달한 유동입니다. 기본 설정의 입구 속도는 그와 다르므로, 첫 단계들에서
유동이 적응합니다. 아래 벽이 미끄러지는 B10-W는 5371단계에서 1.51에 이릅니다. 첫 프레임부터인
6000\~8000단계에서는 정상 실행이 0.43 이하에 머물고, 잘못된 실행 열 개가 0.5를 넘습니다. 이 열 개는
0.81\~2.05인 미끄럼 벽 실행 일곱 개, 23.5인 점성 ×100, 172인 ×300, 0.505인 입구 속도 ×1.5입니다. 표는 실행마다 8000단계에서 세트 여섯 개의 답을 적고, 실행 전체 Courant 최댓값의 단계를 괄호에
적습니다. t0는 온도 0, t07a와 t07b는 온도 0.7에 시드 a와 b입니다. `C`는
`consistent`, `I`는 `inconsistent`이고, 쌍점 뒤는 모델이 말한 원인입니다.

| 실행 | 알려 준 속도, ν(m²/s) | 변경 | Co, 실행 전체(단계) | Co, 6000단계부터 | 알려 줌 t0 | 알려 줌 t07a | 알려 줌 t07b | 알려 주지 않음 t0 | 알려 주지 않음 t07a | 알려 주지 않음 t07b |
|---|---|---|---:|---:|---|---|---|---|---|---|
| B01-N | 37.3 m/s, 2.3e-05 | 없음 | 1.59 (2) | 0.383 | C | I:other | I:walls | I:other | I:other | I:other |
| B01-W | 37.3 m/s, 2.3e-05 | 두 벽 slip | 1.6 (2) | 0.806 | C | C | C | C | C | I:other |
| B02-N | 39.4 m/s, 2.4e-05 | 없음 | 2.32 (2) | 0.387 | C | C | I:walls | I:other | I:walls | I:walls |
| B02-W | 39.4 m/s, 2.4e-05 | ν 2.4e-05 대신 0.00012 m²/s | 2.25 (2) | 0.327 | I:other | I:walls | I:walls | I:other | I:other | I:other |
| B03-N | 29.2 m/s, 2.44e-05 | 없음 | 0.981 (2) | 0.282 | I:other | I:other | C | I:other | I:other | I:walls |
| B03-W | 29.2 m/s, 2.44e-05 | 두 벽 slip | 0.998 (4931) | 0.893 | I:walls | I:walls | I:walls | I:walls | I:walls | I:other |
| B04-N | 38.0 m/s, 2.2e-05 | 없음 | 1.82 (2) | 0.39 | C | I:other | C | I:walls | I:walls | I:walls |
| B04-W | 38.0 m/s, 2.2e-05 | ν 2.2e-05 대신 0.0022 m²/s | 43.9 (41) | 23.5 | I:inlet profile | I:inlet speed | C | I:inlet direction | I:other | I:inlet direction |
| B05-N | 24.8 m/s, 1.66e-05 | 없음 | 2.38 (2) | 0.236 | I:other | I:other | I:walls | I:other | I:other | I:other |
| B05-W | 24.8 m/s, 1.66e-05 | 입구 속도 24.8 대신 19.84 m/s | 4.07 (3) | 0.178 | I:inlet speed | I:inlet speed | I:other | I:other | I:walls | I:other |
| B07-N | 28.9 m/s, 2.08e-05 | 없음 | 1.05 (2) | 0.285 | C | I:other | C | I:other | I:walls | I:inlet direction |
| B07-W | 28.9 m/s, 2.08e-05 | ν 2.08e-05 대신 0.000624 m²/s | 0.983 (3) | 0.202 | I:walls | I:walls | I:other | I:other | I:walls | I:other |
| B08-N | 33.5 m/s, 2.1e-05 | 없음 | 0.367 (2) | 0.345 | C | C | I:other | I:walls | I:inlet direction | C |
| B08-W | 33.5 m/s, 2.1e-05 | 입구 속도 33.5 대신 23.45 m/s | 2.88 (2) | 0.21 | I:inlet speed | I:inlet speed | I:inlet speed | I:walls | I:other | I:inlet direction |
| B09-N | 39.1 m/s, 1.37e-05 | 없음 | 2.18 (2) | 0.426 | C | C | C | C | C | I:other |
| B09-W | 39.1 m/s, 1.37e-05 | lowerWall slip | 2.18 (2) | 1.02 | I:other | I:walls | I:walls | I:other | I:walls | I:inlet direction |
| B10-N | 35.2 m/s, 1.17e-05 | 없음 | 0.991 (2) | 0.389 | C | I:start state | C | C | C | I:viscosity |
| B10-W | 35.2 m/s, 1.17e-05 | lowerWall slip | 1.51 (5371) | 1.26 | C | C | C | I:other | I:other | I:inlet direction |
| B11-N | 30.5 m/s, 1.68e-05 | 없음 | 0.563 (2) | 0.311 | C | I:start state | I:walls | I:other | I:walls | I:walls |
| B11-W | 30.5 m/s, 1.68e-05 | 입구 면 아래 0.75는 속도 0, 나머지는 30.5 m/s | 8.77 (3) | 0.133 | I:inlet speed | I:inlet speed | I:inlet speed | C | I:other | I:walls |
| B12-N | 27.0 m/s, 2.32e-05 | 없음 | 1.69 (2) | 0.261 | I:other | I:other | I:start state | I:walls | I:viscosity | I:walls |
| B12-W | 27.0 m/s, 2.32e-05 | lowerWall slip | 1.69 (2) | 1.08 | I:other | C | I:walls | I:walls | I:walls | I:other |
| B13-N | 24.9 m/s, 2.42e-05 | 없음 | 2.37 (2) | 0.232 | C | I:walls | C | I:walls | I:inlet direction | I:other |
| B13-W | 24.9 m/s, 2.42e-05 | 입구 속도 24.9 대신 2.49 m/s | 11 (3) | 0.223 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:other | I:walls |
| B14-N | 31.4 m/s, 1.22e-05 | 없음 | 0.389 (476) | 0.343 | C | C | C | I:other | I:walls | I:other |
| B14-W | 31.4 m/s, 1.22e-05 | 입구 면 아래 0.25는 속도 0, 나머지는 31.4 m/s | 2.86 (2) | 0.219 | I:inlet speed | I:inlet speed | I:inlet speed | I:walls | I:walls | I:inlet direction |
| B15-N | 20.2 m/s, 1.38e-05 | 없음 | 3.93 (3) | 0.208 | I:other | I:walls | I:other | I:other | I:walls | I:other |
| B15-W | 20.2 m/s, 1.38e-05 | 입구 면 아래 0.5는 속도 0, 나머지는 20.2 m/s | 7.86 (3) | 0.135 | I:inlet speed | I:inlet speed | I:inlet speed | I:walls | C | C |
| B16-N | 31.2 m/s, 1.82e-05 | 없음 | 0.423 (483) | 0.321 | I:other | I:start state | I:walls | I:walls | I:walls | I:walls |
| B16-W | 31.2 m/s, 1.82e-05 | ν 1.82e-05 대신 5.46e-05 m²/s | 0.413 (505) | 0.249 | I:other | I:other | I:walls | I:other | I:other | I:other |
| B17-N | 24.3 m/s, 2.17e-05 | 없음 | 2.55 (2) | 0.231 | C | C | C | I:other | I:other | I:inlet direction |
| B17-W | 24.3 m/s, 2.17e-05 | 입구 속도 24.3 대신 12.15 m/s | 7.05 (3) | 0.141 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:other | I:walls |
| B18-N | 39.2 m/s, 1.78e-05 | 없음 | 2.28 (2) | 0.395 | C | C | I:start state | I:viscosity | I:other | I:other |
| B18-W | 39.2 m/s, 1.78e-05 | 입구 속도 39.2 대신 11.76 m/s | 7.2 (3) | 0.139 | I:inlet speed | I:inlet speed | I:inlet speed | C | I:inlet direction | I:inlet direction |
| B19-N | 33.1 m/s, 1.85e-05 | 없음 | 0.349 (24) | 0.349 | I:other | I:inlet speed | I:other | I:walls | I:walls | I:walls |
| B19-W | 33.1 m/s, 1.85e-05 | 입구 속도 33.1 대신 49.65 m/s | 5.62 (3) | 0.505 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:walls | I:other |
| B20-N | 24.1 m/s, 1.56e-05 | 없음 | 2.6 (2) | 0.221 | I:walls | I:other | I:other | I:walls | I:other | I:walls |
| B20-W | 24.1 m/s, 1.56e-05 | ν 1.56e-05 대신 0.000156 m²/s | 2.55 (3) | 0.195 | I:walls | I:other | I:other | I:other | I:other | I:other |
| B21-N | 24.6 m/s, 2e-05 | 없음 | 2.44 (2) | 0.226 | I:walls | I:inlet direction | C | I:walls | I:other | I:inlet direction |
| B21-W | 24.6 m/s, 2e-05 | ν 2e-05 대신 2e-06 m²/s | 2.45 (2) | 0.276 | I:other | I:other | I:start state | I:walls | I:other | I:other |
| B22-N | 28.4 m/s, 1.93e-05 | 없음 | 1.24 (2) | 0.283 | I:other | I:walls | I:other | I:walls | I:walls | I:viscosity |
| B22-W | 28.4 m/s, 1.93e-05 | ν 1.93e-05 대신 0.00579 m²/s | 379 (25) | 172 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:other | I:other |
| B23-N | 37.8 m/s, 2.23e-05 | 없음 | 1.83 (2) | 0.38 | I:other | I:walls | I:other | I:walls | I:walls | I:other |
| B23-W | 37.8 m/s, 2.23e-05 | lowerWall slip | 1.83 (2) | 0.827 | I:walls | I:walls | I:walls | I:walls | I:walls | I:other |
| B24-N | 38.9 m/s, 1.86e-05 | 없음 | 2.11 (2) | 0.41 | I:other | I:other | I:walls | I:other | I:walls | I:other |
| B24-W | 38.9 m/s, 1.86e-05 | 입구 면 아래 0.25는 속도 0, 나머지는 38.9 m/s | 1.1 (2) | 0.292 | I:inlet speed | I:inlet speed | I:walls | I:walls | I:other | I:other |
| B25-N | 21.5 m/s, 1.41e-05 | 없음 | 3.46 (3) | 0.208 | C | C | C | I:walls | I:walls | I:walls |
| B25-W | 21.5 m/s, 1.41e-05 | 입구 면 아래 0.5는 속도 0, 나머지는 21.5 m/s | 7.61 (3) | 0.152 | I:inlet speed | I:inlet speed | I:inlet speed | C | C | I:walls |
| B26-N | 27.3 m/s, 2.18e-05 | 없음 | 1.59 (2) | 0.267 | C | C | C | I:other | C | I:other |
| B26-W | 27.3 m/s, 2.18e-05 | 입구 면 아래 0.75는 속도 0, 나머지는 27.3 m/s | 9.1 (3) | 0.139 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:other | I:walls |
| B27-N | 26.6 m/s, 1.56e-05 | 없음 | 1.82 (2) | 0.263 | C | I:walls | C | C | C | I:other |
| B27-W | 26.6 m/s, 1.56e-05 | 입구 속도 26.6 대신 33.25 m/s | 0.405 (592) | 0.364 | I:other | I:other | I:other | I:walls | I:other | I:inlet direction |
| B28-N | 34.9 m/s, 1.94e-05 | 없음 | 0.819 (2) | 0.37 | C | I:walls | C | I:walls | I:other | I:walls |
| B28-W | 34.9 m/s, 1.94e-05 | ν 1.94e-05 대신 0.000388 m²/s | 0.744 (3) | 0.247 | I:walls | I:walls | I:walls | I:other | I:other | I:other |
| B29-N | 20.3 m/s, 1.34e-05 | 없음 | 3.9 (3) | 0.21 | C | I:walls | I:walls | I:other | I:other | I:other |
| B29-W | 20.3 m/s, 1.34e-05 | 입구 속도 20.3 대신 4.06 m/s | 10.3 (3) | 0.34 | I:inlet speed | I:inlet speed | I:inlet speed | I:other | I:other | I:other |
| B30-N | 23.5 m/s, 1.44e-05 | 없음 | 2.8 (2) | 0.239 | C | C | I:other | I:other | C | I:other |
| B30-W | 23.5 m/s, 1.44e-05 | 두 벽 slip | 2.8 (2) | 2.05 | C | C | C | I:inlet direction | I:walls | C |

## 설계

계획은 [PLAN.md](PLAN.md)입니다. [design.json](design.json)은 뽑은 설계이며, 뺀 쌍은 `dropped_pairs`에
있습니다. 변경: 입구 속도 ×0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 1.25, 1.5; 점성 ×0.1, 3, 5, 10, 20, 30, 100,
300; `lowerWall` `slip`이 4쌍, 두 벽 `slip`이 3쌍; 입구 면의 아래 0.25, 0.5, 0.75를 속도 0으로, 각각 두 번.
계획의 Deviations에 적은 대로, 점성 ×1000 실행은 발산했습니다. 초안에 있던 입구 방향과 시작 상태는 예비 시험 뒤에 뺐으며, 예비 시험은
[pilot/](pilot/)에 있습니다. 둘 다 표시 영역에 보이는 흔적을 남기지 않습니다.

- **이미지.** 저장한 상태 하나의 |U|와 p를 각각의 색 범위로 솔버의 표시 영역에 그린 단일 필드 이미지
  두 장. `picture_test.render_v2`가 그리는 v2 이미지입니다. 실행마다 6000, 7000, 8000단계: 프레임 174개.
- **프롬프트.** 시스템 프롬프트는 이렇게 말합니다. "The case is a 2D incompressible laminar flow over
  a backward-facing step: a uniform inlet in +x upstream of the plotted part, no-slip stationary walls,
  a zero-gradient outlet, started from a developed state of this flow." 알려 준 조건에서는 이렇게
  이어집니다. "The note gives the intended inlet speed and kinematic viscosity. Judge whether the pictures
  are consistent with this setup." 알려 주지 않은 조건에서는 이렇습니다. "The intended inlet speed and
  viscosity are not given. Judge whether the pictures are consistent with a run of this case set up as
  described." 나머지 프롬프트는 두 조건에서 같습니다. 답으로
  `reason`은 300자 미만, `assessment`는 `consistent`, `inconsistent`, `cannot_tell` 중 하나, `cause`는 `none`,
  `inlet_speed`, `viscosity`, `walls`, `inlet_profile`, `inlet_direction`, `start_state`, `other` 중 하나를
  요구합니다. 알려 준 조건에서는 메모에 기본 설정의 입구 속도와 점성을 담은 `intended_setup`이 있습니다.
  알려 주지 않은 조건의 메모에는 그 항목이 없고, 할 일 줄도 "의도한 설정"이 아니라 "설명한 케이스"와
  맞는지 묻습니다. 한 쌍의 두 실행은 같은 글을 받습니다.
- **요청 설정.** `max_tokens` 320, 프롬프트 캐시 없음, `seed`는 t0에 20261103, t07a에 20261107,
  t07b에 20261108; 온도 0 또는 0.7. 서버: llama.cpp b11429, 문맥 4096, batch와 ubatch 512, 이미지당
  이미지 토큰 상한 256, 요청을 한 번에 하나씩 받는 슬롯 하나([results/server-31b.cmd](results/server-31b.cmd)).
- **채점, 답을 받기 전에 고정.** 정상 실행에 `consistent`, 잘못된 실행에 `inconsistent`라고 답하면
  맞은 것이고, `cannot_tell`은 양쪽 모두 틀린 것입니다. '맞는 이유로 맞음'은 원인까지 그 실행의
  것이어야 하고, 정상 실행의 원인은 `none`입니다. 주 점수는 8000단계 프레임입니다. 검정은 가장 많이 맞힌
  기준선과 견주는 정확한 McNemar 검정이고, 맞힌 비율의 95 % 구간은 쌍 단위 부트스트랩으로 구합니다.
  계획에 따르면 "모델이 규칙보다 낫다"는 결론에는 알려 준 조건, t0의 주 프레임에서 p < 0.05가 필요하고,
  그 밖의 결과는 "보이지 않음"으로 적습니다.
- **기준선**, GPU 작업 전에 `wrong_setup_test2.py baselines`로 계산([baselines.json](baselines.json)).
  상수 기준선은 모든 실행에 `consistent`라고 답합니다. 첫 시험의 최대 |U| 규칙은 표시 영역의 최대 |U|, 곧 색 막대의
  최댓값이 알려 준 속도의 1\~2배 안이면 `consistent`라고 답합니다. 로지스틱 회귀 셋은 한 쌍씩 빼고 맞춥니다.
  그중 색 막대 숫자 기준선은 숫자 다섯, 곧 U 최대와 U 최소를 알려 준 속도로 나눈 값, p 최소와 p 최대를 그 제곱으로 나눈 값,
  알려 준 점성의 로그값을 씁니다. 다른 하나는 여기에 픽셀 비율 셋을 더하고, 나머지 하나는 픽셀 비율 셋만 씁니다.
  첫째와 셋째 픽셀 비율은 |U| 이미지와 p 이미지에서 색 범위의 아래 15 %로 그린 부분의 비율입니다.
  둘째는 그런 |U| 픽셀이 이미지 아래 1/4에서 x 방향으로 닿는 거리를 이미지 폭으로 나눈 값입니다.

## 누출 점검

`build`가 [test-set/leak-check.json](test-set/leak-check.json)을 쓰고, `check`는 GPU 시간을 쓰기 전에
돕니다. 요청 1,044개, 문제 없음. 이미지 데이터와 단계, 시각, `intended_setup` 항목을 빼면 한 세트의
요청 본문 174개는 모두 같은 글입니다. 한 쌍의 두 실행은 알려 준 숫자가 같으므로, 요청 글만 보는 어떤 규칙도
조건마다 정확히 58개 중 29개를 맞힙니다. 어느 요청에도 실행 이름은 없습니다. 정답은 영문 저장소의 [릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/wrong-setup-2-2026-11-03)에 있고, 그 해시는
[test-set/truth.private.sha256](test-set/truth.private.sha256)입니다. 요청 하나의 프롬프트 토큰은
알려 준 조건의 세 세트에서 1,045\~1,049개, 알려 주지 않은 조건의 세 세트에서 1,013\~1,014개였습니다.

## 이미지에 보이는 것

[contact-8000.png](contact-8000.png)에 실행 58개의 8000단계 이미지가 있습니다. 계획을 고정하기 전에 연
이미지는 예비 실행([pilot/](pilot/))의 것뿐이며, 예비 프레임을 본 모델은 없습니다.

- **정상 실행.** 표시 영역 높이의 35\~40 %쯤 위로 빠른 유동, 그 아래로 어두운 선과 점이 있는 느린
  후류, p에는 낮은 압력 핵이 줄지어 있습니다.
- **미끄럼 벽.** 점 대신 매끄러운 층 띠. `lowerWall`이 미끄러지면 아래 가장자리의 유동이 어둡지
  않습니다. |U| 최댓값은 정상 실행과 같고, |U| 최솟값은 일곱 개 중 여섯 개에서 0.026\~0.16 m/s로
  정상 실행의 최대 0.0061 m/s보다 큽니다.
- **점성 ×0.1.** 정상 실행과 같은 모습이며 점과 낮은 압력 핵이 더 많고 더 작습니다.
- **점성 ×3\~×30.** 매끄러운 층, 점 없음, 매끄러운 p. ×100과 ×300은 발달한 유동이 아닙니다. ×300
  실행의 색 막대는 359 m/s에서 끝나고, 알려 준 속도는 28.4 m/s입니다. 바닥을 따라 제트가 보입니다. 25단계에서
  Courant 수 379였고 정상 종료했습니다.
- **입구 속도와 입구 속도 분포.** 정상 실행의 무늬이고 색 막대 숫자가 알려 준 속도와 다릅니다. 속도 분포 변경은
  모양으로는 표시 영역에 닿지 않고, 낮은 유량으로 보입니다.
- 흰 영역이 있는 이미지는 없습니다. 표시 영역이 계단 모서리에서 시작하기 때문입니다.

## 결과

요청 1,044개 모두 올바른 JSON으로 답했고, `cannot_tell`도 오류도 없었습니다. A6000에서 답 하나에 걸린
시간의 중앙값은 4.00 s였고, 작업 71.5분 중 모델 시간은 70.0분이었습니다.
[results/report.md](results/report.md)는 `wrong_setup_test2.py report`의 보고서입니다.
[results/reasons.jsonl](results/reasons.jsonl)에는 세트 여섯 개 모두에서 잘못된 실행의 주 프레임에 낸 `inconsistent` 답
154개가 한 행씩 있습니다. 행마다 이유, 실행의 변경, 말한 원인이 있습니다. 원래 답은 `results/<세트>/metrics.jsonl`에 있습니다.

주 프레임(58개)에서 맞힌 수와, 변경 종류별로 잡은 잘못된 실행 수:

| 답한 쪽 | 알려 줌 | 알려 주지 않음 | 정상 실행 맞힘(알려 줌, 29개 중) | 속도(8개 중) | 점성(8개 중) | 벽(7개 중) | 속도 분포(6개 중) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 상수 | 29 | 29 | 29 | 0 | 0 | 0 | 0 |
| 최대 \|U\| 규칙 | 43 | | 29 | 6 | 2 | 0 | 6 |
| 색 막대 숫자 | 45 | 45 | 28 | 4 | 2 | 7 | 4 |
| 색 막대 숫자와 픽셀 | 44 | 44 | 25 | 4 | 4 | 7 | 4 |
| 픽셀만 | 44 | 44 | 25 | 4 | 5 | 7 | 3 |
| 31B t0 | 44 | 28 | 18 | 8 | 8 | 4 | 6 |
| 31B t07a | 34 | 31 | 9 | 8 | 8 | 3 | 6 |
| 31B t07b | 38 | 28 | 13 | 8 | 7 | 4 | 6 |

속도, 점성, 벽, 속도 분포 열은 알려 준 조건의 수입니다. 알려 주지 않은 조건에서 31B t0는 잘못된 실행 중 속도 7, 점성 8, 벽 6,
속도 분포 4를 잡고 정상 실행 29개 중 3개에 `consistent`라고 답합니다. 알려 준 숫자를 쓰는 회귀는 만든
방식 때문에 두 조건에서 같습니다. 최대 |U| 규칙은 알려 준 속도가 있어야 합니다. 계획은 이 규칙을 알려 준
조건에서만 채점하므로, 그 행의 알려 주지 않음 칸은 비어 있습니다.

알려 줌, 온도 0, 8000단계에서 31B를 기준선 두 개와 견줍니다. 색 막대 숫자 기준선과는 모델만 맞힌 프레임이
13개, 기준선만 맞힌 프레임이 14개입니다(p = 1). 모델이 맞힌 비율의 95 % 부트스트랩 구간은 0.67\~0.84,
기준선은 0.67\~0.88입니다. 상수 기준선과는 모델만 맞힌 프레임이 26개로 모델이 잡은 잘못된 실행이고, 상수만 맞힌 프레임은
오경보 11개입니다. 답에서 계산하면 p = 0.020입니다. 보고서의 상수 기준선 행은 상수와 색 막대 숫자
기준선을 견준 것으로, 17개 대 1개, p = 0.000145입니다.

단계별로 맞힌 수(58개 중), 알려 줌과 알려 주지 않음:

| 세트 | 6000 | 7000 | 8000 |
|---|---:|---:|---:|
| 알려 줌 t0 | 37 | 42 | 44 |
| 알려 줌 t07a | 37 | 32 | 34 |
| 알려 줌 t07b | 35 | 43 | 38 |
| 알려 주지 않음 t0 | 29 | 28 | 28 |
| 알려 주지 않음 t07a | 30 | 27 | 31 |
| 알려 주지 않음 t07b | 28 | 28 | 28 |

8000단계에서 알려 준 세 세트는 58개 중 41개에서 같은 판정을 내고, t0와 t07a는 48개, t0와 t07b는
48개에서 같습니다. 알려 주지 않은 조건에서는 같은 순서로 46, 53, 48개입니다.

## 이유

`results/wrong-setup2-stated-t0/metrics.jsonl`의 8000단계에서 읽음:

- 오경보 11개 중 9개의 이유는 이미지에 후향 계단이 없다고 합니다. "no step geometry (white
  area)", "no sudden expansion or separation zone", "not constrained by a backward-facing step". 하나는
  압력장에 체커보드가 보인다고, 하나는 계단이 없다고는 하지 않고 박리 영역만 없다고 합니다. 말한
  원인은 `other`가 9개, `walls`가 2개입니다.
- `consistent`라고 답한 정상 실행 18개는 모두 계단 뒤의 박리나 재순환 영역을 말하며, 그중 12개는
  최대 속도를 알려 준 속도와 견주기도 합니다. 이 12개 중 6개는 숫자를 적습니다. 4개는 색 막대의
  최댓값을, 2개는 알려 준 속도만 적습니다.
- 입구 속도 실행 8개: 이유 7개는 색 막대의 최댓값을 알려 준 속도와 견줍니다. ×1.25 실행(B27-W)은
  오경보의 문장 "no step geometry (white area)"로 잡히고 원인은 `other`입니다.
- 입구 속도 분포 실행 6개: 이유 모두 색 막대의 최댓값을 알려 준 속도와 견주고 `inlet_speed`라고 합니다.
- 점성 실행 8개: ×3, ×5, ×0.1은 "do not exhibit the characteristic separation and recirculation
  zone", 원인 `other`; ×10, ×20, ×30은 "uniform flow" 또는 "no backward-facing step", 원인 `walls`;
  ×100은 "a jet-like structure", `inlet_profile`; ×300은 359 m/s 최댓값, `inlet_speed`. 점성을 말한 답은
  없습니다.
- 미끄럼 벽 실행 7개: 4개를 잡았습니다. 원인은 `walls` 2개와 `other` 2개이며, `other`는 "a simple channel"입니다. 놓친
  3개, 두 벽 미끄럼 둘과 아래 벽 하나의 답은 "a recirculation zone and reattachment after a step"과
  "consistent with a backward-facing step flow at the given Reynolds number"이며, 그 사이에 압력장
  문장이 있습니다.

## 설계 밖의 확인

- 첫 프레임부터의 가장 큰 Courant 수에 문턱을 두면 오경보 없이 잘못된 실행 29개 중 10개를 잡습니다.
  문턱은 정상 실행의 최댓값인 0.43과 0.5 사이에 둡니다. 잡는 실행은 미끄럼 벽 실행 7개 모두, 점성 ×100과 ×300, 입구 속도
  ×1.5입니다. 이 확인에는 이미지가 아니라 솔버 로그가 필요하고, 문턱은 결과를 본 뒤에 골랐습니다.
- 첫 시험의 실행 전체 Courant 수는 그 시험의 잘못된 실행 다섯 개 중 셋을 오경보 없이 잡았습니다. 여기서는 정상 실행 29개 중
  21개에서 1을 넘습니다. 기본 설정의 입구 속도가 시작 상태의 속도와 다르기 때문입니다.

## 파일

- [PLAN.md](PLAN.md): 예비 시험과 Deviations를 담은 계획. [design.json](design.json): 뺀 쌍을 담은
  설계. [flow-check.json](flow-check.json): 실행 58개의 솔버 점검. [baselines.json](baselines.json):
  기준선의 답. [contact-8000.png](contact-8000.png).
- [pilot/](pilot/): 예비 실행 13개의 설계, 유동 점검, 가시성 측정, 모아 보기 이미지.
- [test-set/](test-set/): 요청마다 해시를 적은 요청 매니페스트, 누출 점검, 정답의 해시. 요청 자체는 파일 1,044개로 하나가 178\~233 KB, 모두 225 MB이며 영문 저장소의
  [릴리스](https://github.com/seungminyome/PythonFOAM/releases/tag/wrong-setup-2-2026-11-03)에 있습니다.
- [results/](results/): `run.json`, 서버 명령, 원래 답을 모두 담은 `metrics.jsonl` 여섯 개, 보고서, 이유.
  `runtime/`에는 llama.cpp 버전, GPU, 모델 파일 해시, gzip 사본의 서버 로그가 있습니다.
- [jobs/](jobs/): 작업 스크립트 셋과 빌드 작업의 출력. [job/sacct.txt](job/sacct.txt)와 gzip 사본의
  GPU 작업 25107731 출력.
- [make_manifest.py](make_manifest.py)는 [manifest.json](manifest.json)을 쓰고, 바이트를 그대로 둔
  파일마다 원본과 비교합니다.
