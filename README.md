# Call of the King: RL_AI

`RL_AI`는 C# 게임 엔진 `SeaEngine`을 Python 강화학습 루프와 연결해,
자기 자신과의 대전, random/greedy 상대, 밸런싱 분석, 서버 접속형 AI 플레이까지
하나의 흐름으로 묶는 프로젝트다.

이 프로젝트의 목표는 단순히 random/greedy를 이기는 모델이 아니라,
선공/후공, 귤/샤를로테, 같은 덱/다른 덱 같은 조건이 바뀌어도 강한 범용 정책을 만드는 것이다.

---

## 현재 구성

```text
RL_AI/start.py
  -> RL_AI/SeaEngine/experiment.py
  -> RL_AI/SeaEngine/trainer.py
  -> RL_AI/SeaEngine/bridge/vector_env.py
  -> RL_AI/SeaEngine/bridge/pythonnet_session.py
  -> RL_AI/SeaEngine/csharp/SeaEngine

RL_AI/make_balance.py
  -> RL_AI/SeaEngine/experiment.py
  -> RL_AI/SeaEngine/evaluator.py
  -> RL_AI/SeaEngine/bridge/pythonnet_session.py

RL_AI/server_ai_client.py
  -> RL_AI/server_protocol.py
  -> RL_AI/SeaEngine/agents.py
  -> RL_AI/SeaEngine/action_adapter.py
  -> server JSON packet
```

핵심 포인트는 다음과 같다.

- 학습은 PythonNet으로 C# DLL을 프로세스 내부에서 직접 호출한다.
- 평가와 분석은 checkpoint별로 side/deck breakdown, 행동 패턴, 기보(history)를 남긴다.
- 서버 플레이는 TCP app-level packet 형식의 JSON 상태를 읽어서 action Uid를 응답한다.
- 로그와 산출물은 `log/`, `models/` 아래에 남기고, 실행별 zip으로 묶는다.

---

## 지금까지 한 일의 큰 줄기

### 1. 학습 파이프라인

`start.py`는 전체 학습과 checkpoint 평가를 담당한다.

흐름은 다음과 같다.

1. `RL_AI.zip`을 찾아 준비한다.
2. `~/RL_AI` 작업 디렉터리를 압축 해제한다.
3. C# 빌드와 PythonNet 초기화를 수행한다.
4. `SeaEnginePPOTrainer`로 학습을 진행한다.
5. 학습 전 random/greedy 평가를 수행한다.
6. 학습을 10,000 episodes 정도 돌린다.
7. checkpoint마다 평가를 수행한다.
8. 학습 후 random/greedy 평가를 수행한다.
9. 결과 로그와 모델을 zip으로 묶는다.

학습은 random, greedy, 최근 self-play를 섞는 커리큘럼이다.

- 초반: random 중심이지만 greedy도 포함
- 중반: random + greedy + 최근 self-play
- 후반: random + greedy + 최근 self-play를 유지하면서 self 비중을 조금씩 늘림

중요한 점은 greedy-heavy fine-tuning이 아니라,
균형과 범용성을 유지하면서 강한 정책을 만드는 것이다.

### 2. 밸런스 파이프라인

`make_balance.py`는 저장된 모델 하나를 따로 평가해서 side/deck 편향을 본다.

기본적으로는:

- `model vs model` self-play
- 총 2000판
- 8개 조합
  - 귤 / 샤를로테
  - 선공 / 후공
  - 같은 덱 / 다른 덱

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

### 3. 서버 접속형 AI 플레이어

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
- 카드 사용 패턴
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

## 최근 상태 요약

최근 모델은 random/greedy에 대해 매우 강해졌고,
self-play balance도 예전처럼 붕괴하지는 않는다.

예시로 최근 balance에서는 다음이 관찰됐다.

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

---

## `start.py` 실행 방법

파일:

- [RL_AI/start.py](RL_AI/start.py)

기본 실행:

```bash
nohup python -u ~/start.py > /dev/null 2>&1 &
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
  - 학습 전/후 평가 판수
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
- checkpoint 평가
- 모델 zip / 로그 zip 정리

---

## `make_balance.py` 실행 방법

파일:

- [RL_AI/make_balance.py](RL_AI/make_balance.py)

기본 실행:

```bash
nohup python -u ~/make_balance.py > /dev/null 2>&1 &
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

향후 서버 이벤트 로깅이 붙으면 다음처럼 확장하기 좋다.

- match start / end
- event trace
- promotion trace
- card summon / destroy
- turn start / end

이 프로젝트는 앞으로도 평균 승률만이 아니라,
기보와 이벤트를 통해 “왜 그렇게 됐는지”를 같이 보는 방향을 유지한다.

---

## 현재 남은 과제

1. 오프닝 루틴 반복을 더 줄이기
2. 프로모션을 더 명시적으로 학습시키기
3. 낮은 사용 카드의 의미를 함께 보기
4. side/deck 편향을 더 정교하게 분해하기
5. 서버 이벤트 로깅과 RL history를 더 자연스럽게 연결하기

