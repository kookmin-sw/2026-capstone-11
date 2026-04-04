# Call of the King Python Prototype

이 디렉터리는 `Call of the King`의 Python 프로토타입 레이어입니다.

현재 목적은 아래 3가지입니다.
- 게임 엔진이 룰북대로 동작하는지 빠르게 검증
- AI vs AI 자동 플레이 로그 생성
- 강화학습 기반 밸런싱 실험의 첫 사이클 구축

장기적으로 실제 게임 로직의 source of truth는 C# 서버가 담당하고, Python은 프로토타입, 테스트, 관측, 학습, 분석 레이어 역할을 담당합니다.

## 핵심 전제

- 마나/코스트 개념은 현재 사용하지 않습니다.
- 카드 원문 텍스트는 최대한 유지합니다.
- 상태의 source of truth는 2D board array가 아니라 `unit registry / unit list` 입니다.
- RL 관점에서 `state`, `action`, `transition`은 엔진이 정의하고, `reward`는 학습 레이어에서 처리합니다.
- 현재 terminal reward는 다음과 같습니다.
  - 승리 `+1`
  - 패배 `-1`
  - 무승부 `0`

## 현재 게임 규칙 요약

- 2인 대전
- 6x6 보드
- 리더가 파괴되면 즉시 패배
- 동시에 패배하면 무승부
- 턴 단계: `START -> MAIN -> END`
- 턴 시작 시 카드 2장 드로우
- 메인 단계 행동:
  - `USE_CARD`
  - `MOVE_UNIT`
  - `UNIT_ATTACK`
  - `END_TURN`
- 턴 종료 시 손패가 3장을 초과하면 3장까지 버림
- 이동과 공격은 별도 행동

## 시작 규칙

- 게임 생성 시 리더 자동 배치
  - P1 리더: `1C`
  - P2 리더: `6D`
- 각 플레이어 시작 손패 3장
- `Turn 1`은 `START`에서 시작
- 첫 턴 시작 시 활성 플레이어도 2장을 추가 드로우합니다.

## 카드 데이터

카드 데이터는 [card_db.py](C:/code/capstone-temp/RL_AI/cards/card_db.py) 가 [Cards.tsv](C:/code/capstone-temp/RL_AI/cards/Cards.tsv) 를 읽어서 `card_db`를 구성합니다.

중요:
- `Cards.tsv`는 실행 위치가 아니라 `card_db.py` 파일 위치 기준으로 읽습니다.
- 현재 프로토타입 엔진은 World `1`, `2`만 지원합니다.
- 전체 TSV에는 더 많은 월드가 있어도, 엔진 쪽 `SUPPORTED_CARD_IDS` 필터를 통과한 카드만 실제 플레이에 사용합니다.

## 디렉터리 구조

- [cards](C:/code/capstone-temp/RL_AI/cards)
  - 카드 데이터 로드
- [game_engine](C:/code/capstone-temp/RL_AI/game_engine)
  - `state.py`: 상태, 액션, 초기 상태 생성
  - `rules.py`: legal action 판정 및 생성
  - `engine.py`: 상태 전이
  - `observation.py`: RL 입력용 observation 생성
- [agents](C:/code/capstone-temp/RL_AI/agents)
  - `base_agent.py`: 공통 인터페이스
  - `random_agent.py`: 무작위 baseline
  - `greedy_agent.py`: 얇은 비랜덤 baseline
  - `rl_agent.py`: PPO 기반 RL 에이전트
- [simulation](C:/code/capstone-temp/RL_AI/simulation)
  - `debug_view.py`: 사람용 콘솔 출력
  - `logging.py`: JSONL/TXT 로그 저장
  - `match_runner.py`: 수동/랜덤/agent vs agent 매치 실행
- [training](C:/code/capstone-temp/RL_AI/training)
  - `storage.py`: rollout 저장
  - `reward.py`: reward 규칙
  - `trainer.py`: PPO 학습 루프
- [tests](C:/code/capstone-temp/RL_AI/tests)
  - 엔진 및 에이전트 테스트
- [log](C:/code/capstone-temp/RL_AI/log)
  - 매치 로그 저장 위치

## 현재 구현 상태

현재 기준으로 아래가 동작합니다.

- `state / rules / engine` 기본 구조
- 리더 자동 배치
- 카드 인스턴스별 runtime unit 분리
- 소환, 이동, 공격, 종료 처리
- 리더 파괴 시 종료 판정
- 수동 매치 실행
- 랜덤 매치 실행
- agent vs agent 매치 실행
- 콘솔 디버그 뷰
- JSONL + TXT 로그 저장
- observation 생성
- PPO 기반 RL 에이전트 골격
- PPO rollout 수집 및 update 루프

## 에이전트 구성

현재 에이전트는 아래와 같습니다.

- `RandomAgent`
  - legal action 중 하나를 무작위 선택
- `GreedyAgent`
  - 공격, 리더 압박, 즉시 킬을 선호하는 얇은 baseline
- `RLAgent`
  - PPO(`Proximal Policy Optimization`) 기반 actor-critic 에이전트
  - 현재는 부분 관측(`Partially Observable`) 전제를 두고 observation을 입력으로 사용합니다.
  - AlphaZero 계열은 아닙니다.

## 강화학습 용어 메모

- `rollout`
  - 에이전트가 실제로 게임을 몇 수 또는 한 판 진행하면서 쌓은 플레이 기록입니다.
  - 강화학습에서는 이 rollout을 학습 데이터처럼 사용해서, 어떤 행동이 좋았는지 나빴는지를 나중에 계산합니다.

- `PPO`
  - `Proximal Policy Optimization`의 줄임말로, 정책을 한 번에 너무 크게 바꾸지 않으면서 안정적으로 학습시키는 강화학습 알고리즘입니다.
  - 지금 프로젝트에서는 "현재 observation에서 어떤 행동을 고를 확률이 좋은지"를 점점 더 낫게 업데이트하는 방식으로 사용합니다.

## 실행 방법

프로젝트 루트 `C:\code\capstone-temp` 에서 실행합니다.

수동 매치:

```powershell
python -m RL_AI.simulation.match_runner
```

랜덤 매치:

```powershell
python -c "from RL_AI.simulation.match_runner import run_random_match; run_random_match(seed=7)"
```

에이전트 vs 에이전트 매치:

```powershell
python -c "from RL_AI.agents.random_agent import RandomAgent; from RL_AI.agents.greedy_agent import GreedyAgent; from RL_AI.simulation.match_runner import run_agent_match; run_agent_match(GreedyAgent(seed=1), RandomAgent(seed=2), seed=7, max_steps=50, print_steps=True)"
```

RLAgent vs RLAgent 매치:

```powershell
python -c "from RL_AI.agents.rl_agent import RLAgent; from RL_AI.simulation.match_runner import run_agent_match; run_agent_match(RLAgent(seed=1), RLAgent(seed=2), seed=7, max_steps=30, print_steps=True, enable_logging=False)"
```

## PPO 학습 실행 예시

아주 짧은 PPO 학습 예시는 아래와 같습니다.

```powershell
python -c "from RL_AI.agents.rl_agent import RLAgent; from RL_AI.agents.random_agent import RandomAgent; from RL_AI.training.trainer import PPOTrainer; agent=RLAgent(seed=1); trainer=PPOTrainer(agent); print(trainer.train(num_episodes=2, opponent_agent=RandomAgent(seed=3), seed=11, max_steps=30))"
```

현재 학습 루프는 다음 순서로 진행됩니다.
- 게임 플레이
- rollout 저장
- terminal reward 부여
- return / advantage 계산
- PPO update

## 로그

기본 로그 저장 위치는 [RL_AI/log](C:/code/capstone-temp/RL_AI/log) 입니다.

생성 파일:
- `*.jsonl`: 분석용 구조화 로그
- `*.txt`: 간단 기보 로그

현재 JSONL 최상위 필드는 다음 2개만 사용합니다.
- `event_type`
- `payload`

기본 이벤트:
- `match_start`
- `action_chosen`
- `state_checkpoint`
- `match_end`

## 테스트 실행

테스트는 [RL_AI/tests](C:/code/capstone-temp/RL_AI/tests) 디렉터리에 있습니다.

엔진 코어 테스트:

```powershell
python -m pytest RL_AI\tests\test_engine_core.py -q
```

greedy agent 테스트:

```powershell
python -m pytest RL_AI\tests\test_greedy_agent.py -q
```

코어 + greedy 테스트:

```powershell
python -m pytest RL_AI\tests\test_greedy_agent.py RL_AI\tests\test_engine_core.py -q
```

## 현재 남은 큰 작업

- self-play 학습 구조 고도화
- 체크포인트 저장 / 불러오기
- 평가 루프 분리
- 고정 action indexing 체계 정리
- observation 추가 정교화
- 밸런스 분석 리포트 연결

## 참고 메모

- `rules.py`는 상태를 바꾸지 않습니다.
- `engine.py`는 상태 전이만 담당합니다.
- `debug_view.py`는 사람용, `logging.py`는 분석용입니다.
- 같은 종류 카드 여러 장은 `card_id`가 아니라 `card_instance_id` 기준으로 구분합니다.
