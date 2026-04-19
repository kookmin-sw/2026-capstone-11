# Call of the King: RL_AI

`RL_AI`는 C# 게임 엔진 `SeaEngine`을 Python 강화학습 루프와 연결해,
자기 자신과의 대전, random/greedy 상대, 밸런싱 분석, 편향 진단, 서버 접속형 AI 플레이까지
하나의 흐름으로 묶는 프로젝트다.

이 프로젝트의 목표는 단순히 random/greedy를 이기는 모델이 아니라,
선공/후공, 귤/샤를로테, 같은 덱/다른 덱 같은 조건이 바뀌어도 강한 범용 정책을 만드는 것이다.

---

## 현재 구성

```text
RL_AI/start.py
  -> RL_AI/training/experiment.py
  -> RL_AI/training/trainer.py
  -> RL_AI/SeaEngine/bridge/vector_env.py
  -> RL_AI/SeaEngine/bridge/pythonnet_session.py
  -> RL_AI/SeaEngine/csharp/SeaEngine

RL_AI/make_balance.py
  -> RL_AI/training/experiment.py
  -> RL_AI/training/evaluator.py
  -> RL_AI/SeaEngine/bridge/pythonnet_session.py

RL_AI/bias_check.py
  -> RL_AI/training/experiment.py
  -> RL_AI/training/evaluator.py
  -> RL_AI/SeaEngine/observation.py
  -> RL_AI/SeaEngine/bridge/pythonnet_session.py

RL_AI/server_ai_client.py
  -> RL_AI/server_protocol.py
  -> RL_AI/agents/seaengine_agents.py
  -> RL_AI/SeaEngine/action_adapter.py
  -> server JSON packet
```

핵심 포인트는 다음과 같다.

- 학습은 PythonNet으로 C# DLL을 프로세스 내부에서 직접 호출한다.
- 평가와 분석은 checkpoint별로 side/deck breakdown, 행동 패턴, 기보(history)를 남긴다.
- 서버 플레이는 TCP app-level packet 형식의 JSON 상태를 읽어서 action Uid를 응답한다.
- 로그와 산출물은 `log/`, `models/` 아래에 남기고, 실행별 zip으로 묶는다.
- `SeaEngine/`에는 엔진과 직접 맞닿는 브리지와 관찰/액션 변환만 남기고,
  agent와 training 로직은 각각 `RL_AI/agents/`, `RL_AI/training/`으로 분리했다.

---

## 실험 순서

### `<start.py>`

학습 전 RL vs random/greedy 8개 조합 50판씩 -> 총 800판  
1~1000판 학습(상대는 커리큘럼에 따라 횟수 다를 수 있음, 정확히 같은 횟수는 기본은 반반이지만 커리큘럼에 따라 조금씩 보정)  
체크포인트 저장  
체크포인트별 평가 400판(greedy 상대로만 8개 조합 50판씩 -> 400판)  
1001~2000판 학습(1~1000판과 동일)  
...  
9001~10000판 학습(1~1000판과 동일)  
체크포인트 저장  
10000판 학습 완료 후에는 체크포인트별 평가는 하지 않음 -> 학습 후 random/greedy로 대  
학습 후 RL vs random/greedy 8개 조합 50판씩 -> 총 800판  
총 15200판

### `<make_balance.py>`

학습된 RL vs 학습된 RL, 8개 조합 250판씩  
총 2000판

### `<bias_check.py>`

random/random 8개 조합 50판씩 -> 400판  
greedy/greedy 8개 조합 50판씩 -> 400판  
RL/RL 8개 조합 50판씩 -> 400판  
canonical/raw 비교 8개 조합 50판씩 -> 800판  
mirror agreement 8개 조합 50판씩 -> 800판  
checkpoint별 side gap -> 5개 체크포인트(2000, 4000, ..., 10000판) 8개 조합 50판씩 -> 2000판  
총 4800판

---

## 분석 방법

### `<start.py>`

1. 학습 전 vs Random, Greedy 8조합 승률 및 정보 전체  
2. 학습 후 vs Random, Greedy 8조합 승률 및 정보 전체  
3. 체크포인트별 vs Random, Greedy 8조합 승률 및 정보 전체  
4. 학습 후 vs Random, Greedy 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `<make_balance.py>`

1. RL vs RL 8조합 승률 및 정보 전체  
2. 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `<bias_check.py>`

1. random vs random 8조합 승률 및 정보 전체  
2. random vs random 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석  
3. greedy vs greedy 8조합 승률 및 정보 전체  
4. greedy vs greedy 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석  
5. RL vs RL 8조합 승률 및 정보 전체  
6. RL vs RL 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석  
7. ablation canonical / raw 8조합 승률 및 정보 전체 비교  
8. mirror canonical / raw 8조합 승률 및 정보 전체 비교  
9. 체크포인트 5개별 선/후공 8조합 승률 및 정보 전체  
10. 체크포인트 5개 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

---

## 지금까지 한 일의 큰 줄기

`RL_AI`는 C# 게임 엔진 `SeaEngine`을 Python 강화학습 루프와 연결해,
자기 자신과의 대전, random/greedy 상대, 밸런싱 분석, 편향 진단, 서버 접속형 AI 플레이까지
하나의 흐름으로 묶는 프로젝트다.

이 프로젝트의 목표는 단순히 random/greedy를 이기는 모델이 아니라,
선공/후공, 귤/샤를로테, 같은 덱/다른 덱 같은 조건이 바뀌어도 강한 범용 정책을 만드는 것이다.

### 1. 학습 파이프라인

`start.py`는 전체 학습과 체크포인트 평가를 담당한다.

흐름은 다음과 같다.

1. `RL_AI.zip`을 찾아 준비한다.
2. `~/RL_AI` 작업 디렉터리를 압축 해제한다.
3. C# 빌드와 PythonNet 초기화를 수행한다.
4. `SeaEnginePPOTrainer`로 학습을 진행한다.
5. 학습 전 `random` / `greedy` 평가를 8개 조합 기준으로 각각 50판씩 수행한다.
6. 학습을 10,000 episodes 돌린다.
7. 1,000 에피소드마다 checkpoint를 저장하고, `1,000 ~ 9,000` 구간의 checkpoint마다 `greedy` 기준 8개 조합 평가를 수행한다.
8. 마지막 10,000 에피소드 checkpoint에서는 추가 checkpoint 평가를 하지 않는다.
9. 학습 후 `random` / `greedy` 평가를 8개 조합 기준으로 각각 50판씩 수행한다.
10. 결과 로그와 모델을 zip으로 묶는다.

여기서 말하는 **8개 조합**은 다음 축의 조합이다.

- 선공 / 후공
- 내 덱: 귤 / 샤를로테
- 상대 덱: 귤 / 샤를로테

학습은 random, greedy, 최근 self-play를 섞는 커리큘럼이다.

- 초반: random 중심이지만 greedy도 포함
- 중반: random + greedy + 최근 self-play
- 후반: random + greedy + 최근 self-play를 유지하면서 self 비중을 조금씩 늘림

중요한 점은 greedy-heavy fine-tuning이 아니라,
균형과 범용성을 유지하면서 강한 정책을 만드는 것이다.

### 2. 밸런스 파이프라인

`make_balance.py`는 저장된 모델 하나를 따로 평가해서 side/deck 편향을 본다.

기본적으로는:

- `RL vs RL` self-play
- 총 2000판
- 8개 조합 x 250판씩
  - 선공 / 후공
  - 내 덱: 귤 / 샤를로테
  - 상대 덱: 귤 / 샤를로테

이 평가에서는 평균 승률만 보지 않는다.

- 최저 조합
- 최대 조합
- spread
- 평균 step
- 평균 final turn
- action type counts
- card use counts
- history

를 함께 본다.

### 3. 편향 진단 파이프라인

`bias_check.py`는 학습이 아니라 모델/표현/대칭성/체크포인트 편향을 분리해서 보는 진단 도구다.

기본적으로 다음을 돌린다.

- `random/random`
- `greedy/greedy`
- `RL/RL`
- canonical/raw 비교
- mirror agreement
- checkpoint side gap

기본 총판수는 `4800`이다.

- `random/random`: 8개 조합 x 50
- `greedy/greedy`: 8개 조합 x 50
- `RL/RL`: 8개 조합 x 50
- canonical/raw: 각 8개 조합 x 50
- mirror agreement: 각 8개 조합 x 50
- checkpoint side gap: 2000 / 4000 / 6000 / 8000 / 10000 checkpoint만 8개 조합 x 50

체크포인트 side gap은 최신 모델 zip에서 episode가 2000, 4000, 6000, 8000, 10000인 파일만 선택한다.

### 4. 서버 접속형 AI 플레이어

`server_ai_client.py`는 게임 서버가 JSON으로 보내는 상태를 읽어서
AI가 action Uid를 응답하는 TCP 클라이언트다.

지원 모드는 다음과 같다.

- `random`
- `greedy`
- `rl`

`rl` 모드는 모델 zip 또는 `.pt`를 직접 읽을 수 있다.

---

## 현재 구조에서 중요한 분석 기준

### 평균보다 편차를 본다

이 프로젝트는 평균 승률만으로 판단하지 않는다.

반드시 같이 본다.

- 선공 vs 후공
- 귤 vs 샤를로테
- 같은 덱 vs 다른 덱
- canonical vs raw
- mirror agreement
- card use patterns
- 오프닝 루틴
- history 기보

이유는 평균 승률이 좋아 보여도,
특정 조건에서 급격히 무너지는 정책일 수 있기 때문이다.

### 루틴 반복을 본다

최근 분석에서 기보는 초반에 꽤 반복적인 패턴을 보여줬다.

- 귤 계열은 `귤 요정`, `망상의 기사님`, `귤 나무`, `귤 직장인?`, `귤 공주님` 쪽으로 굳는 경향이 있었다.
- 샤를로테 계열은 `미스티아`, `아이린`, `릴리아`, `바이올렛`, `샤를로테` 쪽으로 굳는 경향이 있었다.

즉, 모델은 강해졌지만 완전히 자유로운 정책은 아직 아니다.

### 카드 쏠림은 raw count만 보지 않는다

`귤 요정`과 `미스티아`는 3장 복제 카드이므로 단순 사용 횟수만으로 해석하면 안 된다.

앞으로는 다음을 같이 봐야 한다.

- 카드 복제 수로 나눈 normalized use rate
- 낮은 사용 카드
- 카드별 기여도
- 오프닝에서만 쓰이는 카드인지 여부

---

## 이번 런에서 보여준 표 및 해석

### `start.py`

1. 학습 전 vs Random, Greedy 8조합 승률 및 정보 전체
2. 학습 후 vs Random, Greedy 8조합 승률 및 정보 전체
3. 체크포인트별 vs Random, Greedy 8조합 승률 및 정보 전체
4. 학습 후 vs Random, Greedy 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `make_balance.py`

1. `RL vs RL` 8조합 승률 및 정보 전체
2. 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `bias_check.py`

1. `random vs random` 8조합 승률 및 정보 전체
2. `random vs random` 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석
3. `greedy vs greedy` 8조합 승률 및 정보 전체
4. `greedy vs greedy` 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석
5. `RL vs RL` 8조합 승률 및 정보 전체
6. `RL vs RL` 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석
7. `ablation canonical / raw` 8조합 승률 및 정보 전체 비교
8. `mirror canonical / raw` 8조합 승률 및 정보 전체 비교
9. 체크포인트 5개별 선/후공 8조합 승률 및 정보 전체
10. 체크포인트 5개 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### 이번 런의 요약

최근 모델은 random/greedy에 대해 매우 강해졌고,
self-play balance도 예전처럼 붕괴하지는 않는다.

예시로 최근 분석에서는 다음이 관찰됐다.

- overall self-play가 거의 50% 근처
- draw가 크게 감소
- 평균 step과 final turn이 줄어듦
- 한쪽 조합에서 완전히 무너지는 모습은 크게 완화됨

즉, 지금 모델은:

- random을 잘 잡고
- greedy도 꽤 잘 잡고
- side/deck 편향도 예전보다 줄었고
- 아직은 완전 범용은 아니지만, 훨씬 실전형에 가까워졌다

---

## 학습/평가에서 쓰는 주요 결과물

실험이 끝나면 다음이 생성된다.

- `~/RL_AI/log/*.txt`
- `~/RL_AI/log/*.zip`
- `~/RL_AI/models/*.pt`
- `~/RL_AI/models/*.zip`

실행마다 고정적으로 가져가기 쉬운 최신 파일도 만든다.

### `start.py` 실행 후

- `~/start.log`
- `~/RL_AI/log/start_latest.zip`
- `~/RL_AI/models/start_latest.zip`

### `make_balance.py` 실행 후

- `~/make_balance.log`
- `~/RL_AI/log/make_balance_latest.zip`

### `bias_check.py` 실행 후

- `~/bias_check.log`
- `~/RL_AI/log/bias_check_YYYYMMDD_HHMMSS.txt`
- `~/RL_AI/log/bias_check_log_YYYYMMDD_HHMMSS.zip`

---

## `start.py` 실행 방법

파일:

- [RL_AI/start.py](RL_AI/start.py)

기본 실행:

```bash
nohup bash -lc 'cd ~ && python -u ~/start.py' > ~/start.log 2>&1 &
```

자주 쓰는 옵션:

```bash
python -u ~/start.py \
  --eval-matches 50 \
  --train-episodes 10000 \
  --max-turns 100 \
  --update-interval 16 \
  --seed 7
```

옵션 설명:

- `--eval-matches`
  - 학습 전/후 평가 판수 per combo
  - 기본값: `50`
- `--train-episodes`
  - 총 학습 에피소드 수
  - 기본값: `10000`
- `--max-turns`
  - 평가 시 허용 최대 턴 수
  - 기본값: `100`
- `--update-interval`
  - PPO 업데이트 주기
  - 기본값: `16`
- `--seed`
  - 난수 시드
  - 기본값: `7`
- `--skip-unzip`
  - `RL_AI.zip` 압축 해제를 건너뜀
- `--skip-build`
  - C# 빌드를 건너뜀
- `--log-file`
  - 외부 로그 파일 경로를 직접 지정

`start.py`는 다음을 자동으로 처리한다.

- `RL_AI.zip` 준비
- `~/RL_AI/log/` 준비
- C# 빌드
- PythonNet 초기화
- 학습
- before/after 8개 조합 평가
- 1000~9000 checkpoint의 greedy-only 8개 조합 평가
- 모델 zip / 로그 zip 정리

DLPC에서 홈 디렉터리 wrapper를 쓴다면 동일하게 `~/start.py`를 실행하면 된다.

---

## `make_balance.py` 실행 방법

파일:

- [RL_AI/make_balance.py](RL_AI/make_balance.py)

기본 실행:

```bash
nohup bash -lc 'cd ~ && python -u ~/make_balance.py' > ~/make_balance.log 2>&1 &
```

자주 쓰는 옵션:

```bash
python -u ~/make_balance.py \
  --model-path ~/RL_AI/models/model_ep_10000.pt \
  --total-matches 2000 \
  --max-turns 100 \
  --seed 7 \
  --device auto
```

옵션 설명:

- `--model-path`
  - 평가할 모델 파일
  - `.pt` 또는 `.zip` 가능
- `--total-matches`
  - 총 평가 판수
  - 기본값: `2000`
- `--max-turns`
  - 한 판의 최대 턴 수
  - 기본값: `100`
- `--seed`
  - 난수 시드
  - 기본값: `7`
- `--device`
  - `auto`, `cpu`, `cuda`
- `--progress-interval`
  - 진행 로그 출력 간격
- `--log-file`
  - 외부 로그 파일 경로를 직접 지정

`make_balance.py`는 다음 규칙으로 모델을 고른다.

1. `~/RL_AI/models/model_ep_10000.pt`
2. `~/RL_AI/models/*.zip` 중 최신 파일
3. zip 안의 `model_ep_10000.pt`
4. 없으면 zip 안의 최신 `.pt`

`make_balance.py`는 현재 다음을 고정으로 평가한다.

- self-play
- 8개 조합 x 250판
- 총 2000판

DLPC에서 홈 디렉터리 wrapper를 쓴다면 동일하게 `~/make_balance.py`를 실행하면 된다.

---

## `bias_check.py` 실행 방법

파일:

- [RL_AI/bias_check.py](RL_AI/bias_check.py)

기본 실행:

```bash
nohup bash -lc 'cd ~ && python -u ~/bias_check.py' > ~/bias_check.log 2>&1 &
```

자주 쓰는 옵션:

```bash
python -u ~/bias_check.py \
  --total-matches 400 \
  --ablation-matches 400 \
  --mirror-matches 400 \
  --checkpoint-matches 400 \
  --seed 7 \
  --device auto
```

옵션 설명:

- `--model-path`
  - 분석할 모델 파일
  - `.pt` 또는 `.zip` 가능
- `--total-matches`
  - random/random, greedy/greedy, RL/RL 각 suite의 총 판수
  - 기본값: `400`
- `--ablation-matches`
  - canonical/raw 비교용 총 판수
  - 기본값: `400`
- `--mirror-matches`
  - mirror agreement 측정용 총 판수
  - 기본값: `400`
- `--checkpoint-matches`
  - checkpoint side gap 측정용 총 판수
  - 기본값: `400`
- `--checkpoint-limit`
  - checkpoint 개수 제한
  - 기본값: `0` (전체)
- `--parallel-workers`
  - bias task 병렬 프로세스 수
  - 기본값: `0`이면 auto
- `--seed`
  - 난수 시드
  - 기본값: `7`
- `--device`
  - `auto`, `cpu`, `cuda`
- `--skip-unzip`
  - `RL_AI.zip` 압축 해제를 건너뜀
- `--skip-build`
  - C# 빌드를 건너뜀
- `--log-file`
  - 외부 로그 파일 경로를 직접 지정

`bias_check.py`는 다음을 자동으로 처리한다.

- 최신 모델 zip/pt 자동 탐색
- 5개 checkpoint만 추출
  - 2000 / 4000 / 6000 / 8000 / 10000
- random/random, greedy/greedy, RL/RL 평가
- canonical/raw 비교
- mirror agreement 측정
- checkpoint side gap 측정
- 최종 report txt 생성
- bias_check log txt zip 생성

---

## 서버 AI 클라이언트

파일:

- [RL_AI/server_protocol.py](RL_AI/server_protocol.py)
- [RL_AI/server_ai_client.py](RL_AI/server_ai_client.py)

### 패킷 프레이밍

서버는 다음 app-level packet을 쓴다.

1. `int32 payload byte size`  
2. app-level header
   - `uint Flag`
   - `int HandlerNum`
   - `int QueryNum`
   - `int Reserved`
3. `payload`

현재 사용하는 handler:

- `GameMessage = 6`
- `PeerEntrance = 7`

현재 사용하는 flag:

- `None`
- `Respond`
- `Query`

### 서버 AI 플레이 흐름

1. 서버 IP와 port로 TCP 연결
2. 1초 대기
3. `PeerEntrance`로 `"AI Player"` 전송
4. 서버 JSON 상태 수신
5. `GameMessage`의 `Actions`에서 최적의 legal action Uid 선택
6. 같은 query 번호로 `Respond` 전송
7. 게임 종료까지 반복

### JSON 상태 해석

서버 JSON은 다음과 같은 형태를 기대한다.

- `Data.Player1`
- `Data.Player2`
- `Data.Board`
- `Data.ActivePlayerId`
- `Actions[]`

`server_ai_client.py`는 이를 기존 SeaEngine snapshot 형태로 변환해서
기존 `random / greedy / rl` 에이전트가 그대로 action 선택을 하도록 연결한다.

### 실행 예시

```bash
python -m RL_AI.server_ai_client 127.0.0.1 9000 --mode rl --model-path ~/RL_AI/models/model_20260417_155557.zip --device cuda
```

---

## 로깅과 기보

현재 로그는 단순 텍스트가 아니라 분석용 history를 포함한다.

기록되는 것:

- `GameID`
- `context`
- `result`
- `steps`
- `final_turn`
- history
- engine log

`bias_check.py`와 balance 분석은 `SimpleLogger` 기반의 엔진 로그까지 history에 붙여 저장한다.
학습 중 rollout은 무음 logger를 사용하고, 학습 후 평가/분석은 `SimpleLogger`를 사용한다.

이 프로젝트는 앞으로도 평균 승률만이 아니라,
기보와 이벤트를 통해 “왜 그렇게 됐는지”를 같이 보는 방향을 유지한다.

---

## 현재 남은 과제

1. 오프닝 루틴 반복을 더 줄이기
2. 프로모션 관련 feature와 reward의 균형을 더 다듬기
3. 낮은 사용 카드의 의미를 함께 보기
4. side/deck 편향을 더 정교하게 분해하기
5. 서버 이벤트 로깅과 RL history를 더 자연스럽게 연결하기
