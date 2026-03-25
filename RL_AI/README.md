# 강화학습 에이전트 만들기

이 레이어의 목적은 AI vs AI 자동 플레이 로그를 쌓고, 이후 밸런싱 분석 및 학습 실험의 기반을 만드는 것입니다.

장기적으로는 C# 서버가 실제 게임 로직의 source of truth가 되고, 이 Python 코드는 프로토타입, 테스트, 관측, 로그, 분석, 학습 보조 레이어 역할을 담당합니다.

## 현재 핵심 전제

- 카드 원문 텍스트는 최대한 유지합니다.
- 상태의 source of truth는 2D board array가 아니라 `unit registry / unit list` 입니다.
- RL 관점에서 `state`, `action`, `transition`은 엔진이 정의하고, `reward`는 학습 레이어에서 terminal reward로 처리합니다.
- 현재 reward 기준은 다음과 같습니다.
  - 승리 `+1`
  - 패배 `-1`
  - 무승부 `0`
  - 그 외 `0`

## 현재 게임 규칙 요약

- 2인 대전
- 6x6 보드
- 리더가 파괴되면 즉시 패배
- 동시에 패배하면 무승부
- 턴 단계: `START -> MAIN -> END`
- 각 턴 시작 시 카드 2장 드로우
- 메인 단계에서 가능한 행동:
  - `USE_CARD`
  - `MOVE_UNIT`
  - `UNIT_ATTACK`
  - `END_TURN`
- 턴 종료 시 손패가 3장을 초과하면 3장까지 버림
- 이동은 체스 기물 이동 규칙을 따르고, 공격은 이동과 별도 행동입니다.

## 현재 시작 규칙

- 게임 생성 시 리더 자동 배치
  - P1 리더: `1C`
  - P2 리더: `6D`
- 각 플레이어 시작 손패 3장
- 게임은 `Turn 1`, `START`에서 시작
- 첫 턴 시작 시에도 활성 플레이어는 카드 2장을 추가로 드로우합니다.
- 이후 턴도 동일하게 턴 시작 시 2드로우를 수행합니다.

## 카드 데이터

카드 데이터는 [cards/card_db.py](C:/code/capstone-temp/RL_AI/cards/card_db.py) 가 [cards/Cards.xlsx](C:/code/capstone-temp/RL_AI/cards/Cards.xlsx) 를 읽어서 `card_db`를 구성합니다.

중요:
- `Cards.xlsx`는 파이썬 실행 위치 기준이 아니라 `card_db.py` 파일 위치 기준으로 읽습니다.
- 현재는 World `1`, `2`만 지원합니다.
- 현재 지원 카드 수는 총 10장입니다.

## 디렉터리 구조

- [cards](C:/code/capstone-temp/RL_AI/cards)
  - 카드 정의 데이터 로드
- [game_engine](C:/code/capstone-temp/RL_AI/game_engine)
  - `state.py`: 상태, 액션, 초기 상태 생성
  - `rules.py`: 합법 액션 판정과 생성
  - `engine.py`: 상태 전이
- [simulation](C:/code/capstone-temp/RL_AI/simulation)
  - `debug_view.py`: 사람용 콘솔 출력
  - `logging.py`: 분석용 lightweight 로그
  - `match_runner.py`: 수동/랜덤 매치 실행
- [log](C:/code/capstone-temp/RL_AI/log)
  - 매치 실행 결과 JSONL/TXT 로그 저장 위치
- [agents](C:/code/capstone-temp/RL_AI/agents)
  - 에이전트 레이어 초안 위치
- [training](C:/code/capstone-temp/RL_AI/training)
  - 학습 관련 초안 위치
- [analysis](C:/code/capstone-temp/RL_AI/analysis)
  - 로그 분석 관련 초안 위치

## 현재 구현 상태

현재 기준으로 다음이 초안 수준에서 동작합니다.

- `state / rules / engine` 기본 구조
- 리더 자동 배치
- 카드 인스턴스별 runtime unit 분리
- 소환, 이동, 공격, 종료 처리
- 리더 파괴 시 종료 판정
- 수동 매치 실행
- 랜덤 매치 실행
- 콘솔용 디버그 뷰
- JSONL + TXT 기보 로그 저장
- 핵심 엔진 테스트 일부

특히 중요한 설계 원칙은 다음과 같습니다.

- `rules.py`는 상태를 바꾸지 않습니다.
- `engine.py`는 상태 전이만 담당합니다.
- `rules.py`가 `engine.py` 성격의 코드를 가지면 안 됩니다.
- 동일 종류 카드 여러 장은 `card_id`가 아니라 `card_instance_id` 기준으로 구분합니다.

## 실행 방법

프로젝트 루트에서 아래 명령으로 실행합니다.

수동 매치 실행:

```powershell
python -m RL_AI.simulation.match_runner
```

현재 `match_runner.py`의 `__main__`은 수동 매치 실행으로 연결되어 있습니다.

파이썬에서 랜덤 매치 실행:

```python
from RL_AI.simulation.match_runner import run_random_match

run_random_match(seed=7)
```

원하면 아래처럼 직접 짧은 스크립트로 실행할 수 있습니다.

```powershell
python -c "from RL_AI.simulation.match_runner import run_random_match; run_random_match(seed=7)"
```

## 로그 저장 위치

기본 로그 저장 위치는 [RL_AI/log](C:/code/capstone-temp/RL_AI/log) 입니다.

생성 파일:
- `*.jsonl`: 구조화된 분석용 로그
- `*.txt`: 사람이 읽기 쉬운 간단 기보 로그

예시:
- `RL_AI/log/manual_match_20260325_120000.jsonl`
- `RL_AI/log/manual_match_20260325_120000.txt`

현재 JSONL 로그는 대략 다음 이벤트를 저장합니다.
- `match_start`
- `action_chosen`
- `state_checkpoint`
- `match_end`

현재는 `timestamp_utc`는 저장하지 않으며, 최상위 필드는 `event_type`, `payload`만 사용합니다.

## 테스트 실행

테스트는 리포지토리 루트의 [tests](C:/code/capstone-temp/tests) 디렉터리에 있습니다.

엔진 코어 테스트 실행:

```powershell
python -m pytest tests\test_engine_core.py -q
```

전체 테스트 실행:

```powershell
python -m pytest tests -q
```

현재 코어 테스트에서 확인하는 항목:
- 오프닝 세팅
- 이동 규칙
- 공격 처리
- 카드 효과 일부
- `card_instance_id` 분리
- 리더 사망 종료 판정

주의:
- 일부 환경에서는 `pytest` 임시 디렉터리 권한 문제로 로그 테스트가 실패할 수 있습니다.
- 이 경우 게임 로직 실패가 아니라 테스트 실행 환경 문제일 수 있습니다.

## 참고

- 보드 2차원 배열을 source of truth로 삼지 않습니다.
- `debug_view.py`는 사람용, `logging.py`는 분석용입니다.
- 같은 폰 3장은 서로 다른 카드 인스턴스로 다룹니다.
- 지금 목표는 아래 2가지입니다.
  - 룰북대로 엔진이 맞게 동작하는지 빠르게 검증하기
  - AI 자동 플레이 로그를 안정적으로 생산할 수 있는 기반 만들기

## 앞으로 할 일

- `rule_based_agent.py` 초안 작성
- `observation.py` 초안 작성
- 로그 구조 추가 경량화 여부 검토
- 카드 효과 테스트 케이스 확장
- self-play 및 분석 파이프라인 연결