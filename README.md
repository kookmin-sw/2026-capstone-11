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

checkpoint 0 RL vs random/greedy/rule-based/자기자신 8개 조합 100판씩 -> 총 3200판  
1~2000판 학습(상대는 커리큘럼에 따라 횟수 다를 수 있음, 그리고 불리한 시작 상태도 함께 섞어서 학습한다)

- 1~2000판: `normal 80% / slight 15% / heavy 5%`
- 2001~6000판: `normal 70% / slight 20% / heavy 10%`
- 6001~10000판: `normal 60% / slight 25% / heavy 15%`

정의는 다음과 같다.

- `normal`
  - `hp_diff >= -1`
  - `board_diff >= -1`
  - `hand_diff >= -1`
- `slightly deficit`
  - `hp_diff in [-4, -2]` 또는 `board_diff in [-2, -1]`
- `heavy deficit`
  - `hp_diff <= -5` 또는 `board_diff <= -3`
  - 또는 `hp_diff <= -3`이고 `board_diff <= -2`

체크포인트 저장  
2000 / 4000 / 6000 / 8000 checkpoint마다 random / greedy / rule-based / 자기자신 상대로 8개 조합 50판씩 -> 각 checkpoint당 총 1600판  
2001~4000판 학습(12000판과 동일)  
...  
8001~10000판 학습(12000판과 동일)  
체크포인트 저장  
10000판 학습 완료 시 checkpoint 10000 RL vs random/greedy/rule-based/자기자신 8개 조합 100판씩 -> 총 3200판  
총 22800판(학습 10000판 + checkpoint 평가 12800판)

### `<make_balance.py>` (변경 없음)

학습된 RL vs 학습된 RL, 8개 조합 250판씩  
총 2000판

### `<bias_check.py>`

random/random 8개 조합 50판씩 -> 400판  
greedy/greedy 8개 조합 50판씩 -> 400판  
rule-based/rule-based 8개 조합 50판씩 -> 400판  
RL/RL 8개 조합 50판씩 -> 400판  
normalize vs raw 비교 8개 조합 50판씩 -> 800판  
normalize-raw agree rate 8개 조합 50판씩 -> 800판  
random/greedy/rule-based/RL 각각 slight deficit / heavy deficit 8조합 50판씩 -> 3200판  
checkpoint sweep 제외 기본 진단은 총 6400판

---

## 분석 방법

### `<start.py>`

1. checkpoint 0 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체  
2. checkpoint 10000 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체  
3. 체크포인트별 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체  
4. checkpoint 10000 vs Random, Greedy, Rule-based, 자기자신 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `<make_balance.py>`

1. RL vs RL 8조합 승률 및 정보 전체  
2. 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

### `<bias_check.py>`

1. random vs random 8조합 승률 및 정보 전체  
2. greedy vs greedy 8조합 승률 및 정보 전체  
3. rule-based vs rule-based 8조합 승률 및 정보 전체  
4. RL vs RL 8조합 승률 및 정보 전체  
5. 각 family suite의 8조합 별 대표 기보를 보고 패턴 및 판도 분석  
6. normalize vs raw 8조합 승률 및 정보 전체 비교  
7. normalize-raw agree rate 8조합 일치율 및 정보 전체 비교  
8. random, greedy, rule-based, RL의 slight deficit / heavy deficit 8조합 승률 및 정보 전체  
9. 서로 다른 full-run 모델 2개가 있을 때 `--compare-model-path`로 모델 A vs 모델 B 편향 비교

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
5. checkpoint 0 `random` / `greedy` / `rule-based` / `자기자신` 평가를 8개 조합 기준으로 각각 100판씩 수행한다.
6. 학습을 10,000 episodes 돌린다.
7. 2,000 에피소드마다 checkpoint를 저장하고, `2,000 / 4,000 / 6,000 / 8,000` checkpoint마다 `random` / `greedy` / `rule-based` / `자기자신` 기준 8개 조합 평가를 수행한다.
8. 10,000 에피소드 checkpoint에서는 `random` / `greedy` / `rule-based` / `자기자신` 평가를 8개 조합 기준으로 각각 100판씩 수행한다.
9. checkpoint 10000 평가를 마치면 결과 로그와 모델을 zip으로 묶는다.

여기서 말하는 **8개 조합**은 다음 축의 조합이다.

- 선공 / 후공
- 내 덱: 귤 / 샤를로테
- 상대 덱: 귤 / 샤를로테

학습은 random, greedy, rule-based, 최근 self-play를 섞는 커리큘럼이다.

- opponent pool은 기본적으로 `random / greedy / rule-based / 최근 self-play`를 섞고,
  checkpoint가 쌓일수록 recent self-play 비중이 늘어난다.
- `greedy`는 오래된 단순 공격 우선 로직에서 벗어나, 킬각/리더 압박/중앙 점유/전개 우선순위를 더 보는 tactical greedy로 강화했다.
- `rule-based`는 search 없이 한 수의 전술 가치를 더 촘촘히 평가하는 강한 기준 agent다. 공식 agent 종류는 `random / greedy / rule-based / RL` 네 가지로 유지한다.
- deficit start schedule은 초반에 가장 안전하게(`normal` 위주) 시작하고,
  학습이 진행될수록 `slight`, `heavy` 비중을 천천히 늘린다.
- training layout은 기본값이 `balanced`라서 8개 조합을 고르게 본다.
  필요할 때만 `adaptive` 또는 `focused` 모드로 바꿔서 약한 조합을 더 자주 보게 할 수 있다.
- opening diversity는 랜덤 노이즈뿐 아니라 `SEAENGINE_OPENING_TEACHER_PROB` 기반의 rule-based opening teacher를 섞어 고착화를 줄인다.
- imitation learning은 초반 teacher가 고른 행동에 작은 behavior cloning loss를 추가하는 방식으로 들어갔다. 기본값은 작게 잡아서 RL의 자유도를 크게 훼손하지 않는다.
- hard example mining은 deficit start와 focused/adaptive layout, 그리고 checkpoint 하락 시 recovery schedule로 반영한다.
- population-based checkpoint selection은 greedy/self 평가를 바탕으로 평균 승률, worst combo, side gap을 합쳐 checkpoint score를 남기는 방식으로 기록한다.

중요한 점은 greedy-heavy fine-tuning이 아니라,
균형과 범용성을 유지하면서 강한 정책을 만드는 것이다.
최근에는 샤를로테 전용 shaping을 줄이고, 덱 공통의 오프닝 개발/리더 보호 shaping으로 정리했다.

최근 바뀐 정책은 다음처럼 이해하면 된다.

- 예전에는 샤를로테 약점 보강을 위해 layout 샘플링이 한쪽으로 기울 수 있었지만,
  지금은 기본값이 `balanced`라서 8개 조합을 고르게 본다.
- 약한 조합을 더 보고 싶을 때만 `adaptive` 또는 `focused` 모드를 켠다.
- reward shaping은 특정 덱 전용 보정보다, 모든 덱에 공통인 초반 개발/리더 보호/불필요한 TurnEnd 억제 쪽으로 옮겼다.
- 기록용 history는 모든 판을 다 저장하지 않고, 대표 샘플만 남기는 구조를 유지한다.

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
- `normalize vs raw`
- `normalize-raw agree rate`
- `random/greedy/rule-based/RL` 각각 `slight deficit / heavy deficit`
- 필요하면 `--compare-model-path`로 서로 다른 full-run 모델 2개를 직접 head-to-head 비교한다.

checkpoint sweep을 제외한 기본 총판수는 `6400`이다.

- `random/random`: 8개 조합 x 50
- `greedy/greedy`: 8개 조합 x 50
- `RL/RL`: 8개 조합 x 50
- `normalize vs raw`: 각 8개 조합 x 50
- `normalize-raw agree rate`: 각 8개 조합 x 50
- `random/greedy/rule-based/RL`의 `slight deficit / heavy deficit`: 각 8개 조합 x 50
- `--compare-model-path`를 준 경우: 모델 A vs 모델 B 8개 조합 x 50

### 4. 서버 접속형 AI 플레이어

`server_ai_client.py`는 게임 서버가 JSON으로 보내는 상태를 읽어서
AI가 action Uid를 응답하는 TCP 클라이언트다.

지원 모드는 다음과 같다.

- `random`
- `greedy`
- `rule_based`
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
- normalize vs raw
- normalize-raw agree rate
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

1. 학습 전 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체
2. 학습 후 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체
3. 체크포인트별 vs Random, Greedy, Rule-based, 자기자신 8조합 승률 및 정보 전체
4. 학습 후 vs Random, Greedy, Rule-based, 자기자신 8조합 별 기보를 5개씩 보고 패턴 및 판도 분석

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
7. `normalize vs raw` 8조합 승률 및 정보 전체 비교
8. `normalize-raw agree rate` 8조합 일치율 및 정보 전체 비교
9. `random vs 자기자신`, `greedy vs 자기자신`, `rule-based vs 자기자신`, `학습이 완료된 RL vs 자기자신` `slight deficit / heavy deficit` 8조합 승률 및 정보 전체
10. `random vs 자기자신`, `greedy vs 자기자신`, `rule-based vs 자기자신`, `학습이 완료된 RL vs 자기자신` `slight deficit / heavy deficit` 8조합 기보를 5개씩 보고 패턴 및 판도 분석

### 이번 런의 요약

최신 런 기준으로 정리하면 다음과 같다.
핵심 변화는 `greedy` 강화, `rule-based` 기준 agent 추가, opening diversity / imitation learning / hard example mining / population-based checkpoint score,
리더 최소 HP 통계 추가, 그리고 로그 산출물 통합이다.

`start.py` 기준 학습 후 8조합 전체 승률은 다음과 같다.

- vs Random: 약 90.0%
- vs Greedy: 약 57.2%
- vs Rule-based: 약 54.8%
- vs Self: P1 45.8% / P2 54.2%

해석은 다음과 같다.

- 예전의 greedy 62%대보다 낮아진 것은 단순 greedy 전용 최적화가 아니라 `rule-based`, self-play, 불리한 시작 상태, opening diversity까지 같이 보도록 목표가 넓어졌기 때문이다.
- 최종 모델은 random은 안정적으로 이기지만, greedy/rule-based를 80~90%로 압도하는 수준은 아직 아니다.
- population score 기준으로는 최종 10000 checkpoint보다 중간 checkpoint가 더 균형적일 수 있으며, 최근 분석에서는 6000 checkpoint가 비교적 안정적으로 보였다.
- 샤를로테, 특히 `샤를로테/후공/다른 덱` 약점은 여전히 강하게 남아 있다.

`make_balance.py` 기준 RL vs RL 2000판 결과는 다음과 같다.

- 전체 RL 승률: 48.65%
- RL wins / opponent wins / draws: 973 / 1027 / 0
- 평균 steps: 약 130.78
- 평균 final turn: 약 13.95
- 전체적으로는 50%에 가깝지만, 8조합별 편차는 크다.
- `귤/선공/다른 덱`은 82.4%로 강하고, `샤를로테/후공/다른 덱`은 14.4%로 매우 약하다.

리더 최소 HP 통계도 기록한다.

- make_balance 전체 aggregate:
  - Orange 평균 최소 HP: 1.98, min -2, max 7
  - Charlotte 평균 최소 HP: 1.31, min -2, max 10
- `샤를로테/후공/다른 덱`에서는 Charlotte 평균 최소 HP가 0.14까지 내려가서 거의 끝까지 몰리는 판이 많다.
- history로 저장된 대표 판에서는 각 판별 `leader_hp=P1:... final=... min=... | P2:... final=... min=...` 형태로 볼 수 있다.
- 단, 기본 history sampling 때문에 모든 판의 per-match HP가 저장되는 것은 아니고, summary에는 전체 통계가 저장된다.

`bias_check.py` 기준 주요 관찰은 다음과 같다.

- random, greedy, rule-based, RL family 모두에서 Orange가 Charlotte보다 평균 최소 HP가 높은 경향이 반복된다.
- RL/RL 기준 평균 최소 HP는 Orange 1.93, Charlotte 1.37이다.
- rule-based/rule-based 기준 평균 최소 HP는 Orange 2.29, Charlotte 1.19로, 모델만의 문제가 아니라 게임/덱 구조 편향도 섞여 있을 가능성이 높다.
- normalize canonical은 raw보다 극단성이 낮고, raw는 특정 조합에서 더 강하거나 더 치우치는 경향이 있다.
- checkpoint별로는 6000 checkpoint의 Charlotte 평균 최소 HP가 0.92로 낮고, 8000 checkpoint는 Orange/Charlotte 차이가 상대적으로 완화된다.

즉, 지금 모델은 random을 안정적으로 이기고 greedy/rule-based 상대로도 절반 이상을 가져가지만,
일반 사용자 수준의 안정적인 범용 플레이를 목표로 하려면 샤를로테 약점, side/deck 편차, 오프닝 고착화를 계속 줄여야 한다.

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
- `~/RL_AI/log/start_summary.txt`

### `make_balance.py` 실행 후

- `~/make_balance.log`
- `~/RL_AI/log/make_balance_latest.zip`
- `~/RL_AI/log/make_balance_summary.txt`

### `bias_check.py` 실행 후

- `~/bias_check.log`
- `~/RL_AI/log/bias_check_latest.zip`
- `~/RL_AI/log/bias_check_summary.txt`

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
  - checkpoint 0/10000 평가 판수 per combo (random/greedy/rule-based/self 각각)
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
- checkpoint 0 / 10000 8개 조합 평가
- 2000/4000/6000/8000 checkpoint의 greedy/rule-based/self 8개 조합 평가
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
  - random/random, greedy/greedy, rule-based/rule-based, RL/RL 각 suite의 총 판수
  - 기본값: `400`
- `--comeback-matches`
  - greedy/rule-based/self slight/heavy deficit suite의 총 판수
  - 기본값: `200`
- `--ablation-matches`
  - normalize vs raw 비교용 총 판수
  - 기본값: `400`
- `--mirror-matches`
  - normalize-raw agree rate 측정용 총 판수
  - 기본값: `400`
- `--checkpoint-matches`
  - checkpoint 비교용 총 판수
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
- normalize vs raw 비교
- normalize-raw agree rate 측정
- random/greedy/rule-based/RL deficit suite 측정
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

기보 저장은 각 시나리오의 전체 판수 기준으로 1/5 정도를 대표 샘플로 남기고,
승/패/무가 실제 존재하면 최소 1개는 반드시 포함되도록 한다.

이 프로젝트는 앞으로도 평균 승률만이 아니라,
기보와 이벤트를 통해 “왜 그렇게 됐는지”를 같이 보는 방향을 유지한다.

---

## 현재 남은 과제

1. 오프닝 루틴 반복을 더 줄이기
2. 프로모션 관련 feature와 reward의 균형을 더 다듬기
3. 낮은 사용 카드의 의미를 함께 보기
4. side/deck 편향을 더 정교하게 분해하기
5. 서버 이벤트 로깅과 RL history를 더 자연스럽게 연결하기
