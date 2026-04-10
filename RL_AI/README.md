# RL_AI

`RL_AI`는 `Call of the King`의 실험/학습 레이어입니다.  
지금 기준의 실제 게임 로직 source of truth는 Python 프로토타입이 아니라 **C# SeaEngine**이고, Python은 그 위에서:

- C# 엔진 실행
- 상태 관측 변환
- 에이전트 선택
- PPO 학습
- 평가 / 리포트 저장

을 담당합니다.

## 현재 구조

핵심 디렉터리:

- [SeaEngine](C:/code/capstone-temp/RL_AI/SeaEngine)
  - C# SeaEngine 브리지, observation, RL trainer/evaluator
- [SeaEngine/csharp/SeaEngine](C:/code/capstone-temp/RL_AI/SeaEngine/csharp/SeaEngine)
  - 복사된 C# 게임 엔진
- [SeaEngine/csharp/SeaEngineCli](C:/code/capstone-temp/RL_AI/SeaEngine/csharp/SeaEngineCli)
  - Python이 C# 엔진과 통신하기 위한 CLI 브리지
- [simulation/match_runner.py](C:/code/capstone-temp/RL_AI/simulation/match_runner.py)
  - Python legacy 엔진 매치 러너 + SeaEngine 매치 러너 통합 진입점
- [start.ipynb](C:/code/capstone-temp/RL_AI/start.ipynb)
  - DLPC에서 실행하는 기본 notebook
- [cards/Cards.csv](C:/code/capstone-temp/RL_AI/cards/Cards.csv)
  - 카드 데이터
- [log](C:/code/capstone-temp/RL_AI/log)
  - 평가 / 학습 리포트 저장 위치

legacy Python 엔진 파일은 별도 보관되어 있고, 현재 SeaEngine 실험과는 분리되어 있습니다.

## 실제 호출 흐름

현재 SeaEngine 기준 흐름은 이렇습니다.

```text
start.ipynb
  -> RL_AI.SeaEngine.experiment.run_train_eval_experiment()
    -> SeaEnginePPOTrainer / evaluator
      -> SeaEngineSession
        -> SeaEngineCli
          -> C# SeaEngine Game
```

조금 더 풀면:

1. Python이 [seaengine_session.py](C:/code/capstone-temp/RL_AI/SeaEngine/bridge/seaengine_session.py) 로 `SeaEngineCli` 프로세스를 띄움
2. `SeaEngineCli`가 C# `Game` 객체를 메모리에 유지
3. Python은 `init / snapshot / apply / close` 요청만 JSON으로 주고받음
4. snapshot은 [observation.py](C:/code/capstone-temp/RL_AI/SeaEngine/observation.py) 에서 RL 입력으로 변환됨
5. [agents.py](C:/code/capstone-temp/RL_AI/SeaEngine/agents.py) 의 `Random / Greedy / RL` 에이전트가 action을 선택
6. [trainer.py](C:/code/capstone-temp/RL_AI/SeaEngine/trainer.py) 가 rollout 수집 + PPO update
7. [evaluator.py](C:/code/capstone-temp/RL_AI/SeaEngine/evaluator.py) 가 다회전 평가 후 리포트 저장

## 매치 러너

통합된 진입점:
- [match_runner.py](C:/code/capstone-temp/RL_AI/simulation/match_runner.py)

여기서 두 종류를 모두 다룹니다.

- 기존 Python 프로토타입 엔진
  - `run_manual_match`
  - `run_random_match`
  - `run_agent_match`
- C# SeaEngine 엔진
  - `run_cs_manual_match`
  - `run_cs_random_match`
  - `run_cs_agent_match`
  - `run_cs_mixed_match`
  - `run_cs_manual_vs_agent`

호환용으로 [cs_match_runner.py](C:/code/capstone-temp/RL_AI/simulation/cs_match_runner.py) 도 남아 있지만, 앞으로는 `match_runner.py` 기준으로 보면 됩니다.

## DLPC 실행

기본 notebook:
- [start.ipynb](C:/code/capstone-temp/RL_AI/start.ipynb)

현재 notebook이 하는 일:

1. `dotnet` 확인 / 설치
2. 현재 notebook kernel에 `torch`, `numpy`, `pytest`가 없으면 설치
3. `RL_AI.zip` 압축 해제
4. `SeaEngineCli` 빌드
5. SeaEngine 기준 학습 전/후 평가 실험 실행

중요:
- notebook의 Python 셀은 **현재 kernel Python**을 사용합니다
- 그래서 패키지 설치는 `sys.executable -m pip install -I ...` 기준으로 처리합니다

## 기본 실험 함수

현재 주로 쓰는 함수:
- [run_train_eval_experiment](C:/code/capstone-temp/RL_AI/SeaEngine/experiment.py)
- [run_checkpoint_training_experiment](C:/code/capstone-temp/RL_AI/SeaEngine/experiment.py)

### `run_train_eval_experiment(...)`

한 번에 아래를 수행합니다.

1. 학습 전 `RL vs Random`
2. 학습 전 `RL vs Greedy`
3. mixed opponent 학습
4. 학습 후 `RL vs Random`
5. 학습 후 `RL vs Greedy`

진행률은 화면에 출력되고, 요약은 자동으로 저장됩니다.

예시:
```python
from RL_AI.SeaEngine.experiment import run_train_eval_experiment

result = run_train_eval_experiment(
    eval_matches=100,
    train_episodes=1000,
    max_turns=100,
    update_interval=8,
    seed=7,
)
print(result["report_path"])
```

### `run_checkpoint_training_experiment(...)`

긴 학습을 여러 checkpoint로 나누어 평가합니다.

예시:
```python
from RL_AI.SeaEngine.experiment import run_checkpoint_training_experiment

checkpoint = run_checkpoint_training_experiment(
    eval_matches=100,
    total_train_episodes=1000,
    eval_interval=200,
    max_turns=100,
    update_interval=8,
    seed=7,
)
print(checkpoint["summary_report_path"])
```

사람 vs agent 수동 대전 예시:
```python
from RL_AI.SeaEngine.agents import SeaEngineGreedyAgent
from RL_AI.simulation.match_runner import run_cs_manual_vs_agent

run_cs_manual_vs_agent(
    SeaEngineGreedyAgent(seed=1),
    human_player="P1",
    max_turns=100,
    print_steps=True,
)
```

혼합 수동/자동 대전 예시:
```python
from RL_AI.SeaEngine.agents import SeaEngineRLAgent
from RL_AI.simulation.match_runner import run_cs_mixed_match

run_cs_mixed_match(
    p1_controller=None,  # manual
    p2_controller=SeaEngineRLAgent(seed=1),
    max_turns=100,
    print_steps=True,
)
```

## 리포트 저장

저장 위치:
- [log](C:/code/capstone-temp/RL_AI/log)

주요 파일:
- `seaengine_evaluation_report_*.txt`
- `seaengine_train_eval_report_*.txt`
- `seaengine_checkpoint_training_report_*.txt`

`run_train_eval_experiment(...)` 요약 리포트에는 아래 시간도 함께 저장됩니다.

- `before_random_time_sec`
- `before_greedy_time_sec`
- `train_time_sec`
- `after_random_time_sec`
- `after_greedy_time_sec`
- `total_time_sec`

## 현재 학습 결과 해석

2026-04-10 기준으로 확인된 상태:

- `Greedy > Random`
- `RL > Random`
- 아직 `RL < Greedy`

즉 RL은 기본 플레이는 배웠지만, 아직 Greedy baseline을 넘지는 못했습니다.

대표적인 최근 결과:

- 학습 전 `RL vs Random`: `78%`
- 학습 후 `RL vs Random`: `92%`
- 학습 전 `RL vs Greedy`: `19%`
- 학습 후 `RL vs Greedy`: `25%`

해석:

- mixed opponent 학습은 실제로 효과가 있음
- Random 상대 승률은 크게 올랐음
- Greedy 상대도 개선은 있었지만 아직 충분하지 않음

## observation / action feature 현 상태

현재 [observation.py](C:/code/capstone-temp/RL_AI/SeaEngine/observation.py)는 이전보다 더 많은 정보를 씁니다.

상태 벡터에 들어가는 정보 예:

- 턴 / active player / result
- 손패 수, 덱 수, 트래시 수
- 리더 체력 비율과 체력 차이
- 보드 유닛 수 / 공격력 총합 / 준비된 유닛 수
- deploy 가능 손패 수
- skill action 수
- attack / move action 수
- 리더에 대한 위협 수
- 중앙 지역 점유 수
- 보드 카드별:
  - 위치
  - 체력 / 공격력 / 효과 공격력
  - 이동 / 공격 상태
  - 상태이상 요약
  - 적 리더와 거리
  - 인접 적 수
  - 들어오는 공격자 수
  - 실제 공격/이동 action 보유 여부

action feature에 들어가는 정보 예:

- effect type / target type
- source 유닛 스탯
- target 유닛 스탯
- 이동 전후 리더 거리
- 리더 존 진입 여부
- 즉시 킬 가능 여부
- 리더 위협 여부
- 두 대상 액션 여부
- 교환 후 생존 가능성 추정
- 저체력 타깃 여부
- 손패에서 나가는 행동인지 여부

## 아직 개선 여지가 큰 부분

지금도 개선 여지는 많습니다.

가장 큰 후보:

1. **self-play**
   - 현재는 `random + greedy` mixed opponent가 기본
   - 여기에 이전 checkpoint RL을 섞으면 일반화에 더 좋을 가능성이 큼

2. **best checkpoint 선택**
   - 마지막 모델보다 중간 checkpoint가 더 좋은 경우가 있을 수 있음

3. **leader pressure / tactical exchange feature 추가 정교화**
   - 현재도 들어가 있지만 더 정교한 “다음 턴 킬 각” 정보를 넣을 수 있음

4. **학습 속도 최적화**
   - 가장 큰 병목은 GPU보다 **C# 엔진 호출 / snapshot 왕복 비용**일 가능성이 큼

## 학습 속도가 느린 이유와 현재 개선

1000 episode가 40분 안팎 걸리는 가장 큰 이유는, 연산보다도:

- C# SeaEngine 프로세스
- Python <-> C# 브리지
- snapshot JSON 직렬화/파싱

비용이 큽니다.

이번에 이미 한 개선:

- [trainer.py](C:/code/capstone-temp/RL_AI/SeaEngine/trainer.py)
  - episode마다 `SeaEngineSession`을 새로 띄우지 않고, 학습 루프 동안 재사용
- [evaluator.py](C:/code/capstone-temp/RL_AI/SeaEngine/evaluator.py)
  - 평가 매치마다 프로세스를 새로 띄우지 않고, 평가 루프 동안 재사용

이건 환경과 상관없이 실제로 시간을 줄이는 방향입니다.

그래도 남는 병목:

- snapshot 전체를 매 step Python으로 넘기는 구조
- legal action 수가 많을 때 action feature 계산 비용
- PPO가 step 단위로 모든 action set을 다시 평가하는 비용

## 사람이랑 붙이기

아직 notebook에는 넣지 않았지만, SeaEngine 기준으로 사람 vs agent도 가능합니다.

함수:
- [run_cs_manual_vs_agent](C:/code/capstone-temp/RL_AI/simulation/match_runner.py)
- [run_cs_mixed_match](C:/code/capstone-temp/RL_AI/simulation/match_runner.py)

예시:
```python
from RL_AI.SeaEngine.agents import SeaEngineGreedyAgent
from RL_AI.simulation.match_runner import run_cs_manual_vs_agent

run_cs_manual_vs_agent(
    SeaEngineGreedyAgent(seed=1),
    human_player="P1",
    max_turns=100,
    print_steps=True,
)
```

## 용어 메모

- `episode`
  - 게임 한 판 전체
- `turn`
  - 한 플레이어의 턴
- `step`
  - 행동 1회
- `rollout`
  - 학습용으로 쌓은 플레이 기록

## 현재 권장 다음 단계

지금 상태에서 가장 자연스러운 다음 수순:

1. `checkpoint` 기준으로 best model 찾기
2. opponent pool에 self-play 추가
3. Greedy 비중을 높인 mixed training 실험
4. `RL vs Greedy` 100판 평가 반복

즉 지금 병목은 엔진보다도 **정책 품질과 학습 효율** 쪽입니다.
