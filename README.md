# 👑 Call of the King: RL_AI (SeaEngine Edition)

`RL_AI`는 C# 기반 보드게임 엔진 **SeaEngine** 위에서 동작하는 최첨단 강화학습 실험 레이어입니다.  
현재 프로젝트는 단순한 로직 구현을 넘어, **병렬 데이터 수집**과 **비동기 통신**을 통한 학습 가속화 단계에 도달해 있습니다.

---

## 🏗️ 시스템 아키텍처

현재 시스템은 **Python(지능)**과 **C#(육체)**이 분리된 하이브리드 구조입니다.

```text
[ start.ipynb ] (User Interface)
      ↓ (await)
[ experiment.py ] (Global Loop & Checkpointing)
      ↓ (async)
[ trainer.py ] (PPO Algorithm & Rollout Management)
      ↓ (await)
[ VectorSeaEngineEnv ] (Parallel Environment Manager)
      ↓ (Multi-Process IPC)
[ SeaEngineCli (C#) ] × 8 Engines (Concurrent Simulation)
```

### ⚡ 핵심 기술적 특징
- **Vectorized Environment**: 8개 이상의 C# 엔진을 동시에 구동하여 데이터를 병렬로 수집합니다.
- **Batched Inference**: 병렬 환경의 상태를 하나로 묶어 GPU에서 한 번에 추론하여 효율을 극대화했습니다.
- **Pure Async Architecture**: 주피터 노트북의 루프 충돌 문제를 해결하기 위해 전체 파이프라인을 `async/await` 기반의 순수 비동기로 재설계했습니다.
- **Automated Log Management**: 실험 종료 시 생성된 로그를 자동 압축(.zip)하고 정리하여 저장 공간을 효율적으로 관리합니다.

---

## 📁 디렉토리 구조 (Standardized)

- **[SeaEngine/](RL_AI/SeaEngine)**: C# 엔진 브리지 및 관측(Observation) 변환 로직
  - `bridge/`: `VectorEnv`, `SeaEngineSession` (IPC 통신 핵심)
  - `csharp/`: 실제 C# 게임 엔진 소스 코드 및 CLI
- **[training/](RL_AI/training)**: 강화학습 핵심 알고리즘
  - `trainer.py`: PPO 트레이너 (비동기 최적화)
  - `reward.py`: 지능형 보상 함수 (HP 격차 및 효율성 평가)
  - `storage.py`: 데이터 수집 버퍼
- **[simulation/](RL_AI/simulation)**: 매치 실행 및 평가 도구
  - `evaluator.py`: 16방향 정밀 매트릭스 평가기 (Mirror/Counter Match 지원)
  - `match_runner.py`: 통합 매치 실행 진입점
- **[models/](RL_AI/models)**: 학습된 최적의 모델(`pt`) 저장소
- **[log/](RL_AI/log)**: 리포트 및 매치 로그 (자동 압축 관리)

---

## ⚖️ 밸런스 패치 (Current Baseline)

공정한 학습 환경을 위해 **'귤 덱'**의 수치를 다음과 같이 조정하였습니다.

| 카드 ID | 이름 | Atk | HP | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **Or_L** | 귤 공주님 | 3 | **7** | 리더 유지력 조정 |
| **Or_B** | 귤 직장인? | 1 | **3** | 워프 기동 리스크 강화 |
| **Or_K** | 망상의 기사님 | 2 | **2** | 전투 효율 정상화 |
| **Or_P** | 귤 요정 | 1 | 1 | 자원 수급 전용 |

---

## 📊 평가 지표 및 분석

학습 후 실행되는 **Deep Analytics**를 통해 다음 지표를 추적합니다.
1. **Mirror Match Win Rate**: 동일 덱 조건에서 상대(Greedy)보다 얼마나 영리한가? (진정한 지능의 척도)
2. **Counter Match Win Rate**: 덱 상성을 전략으로 극복하고 있는가?
3. **Avg Interaction Steps**: 게임이 단순 암살이 아닌 정석적인 운영 싸움으로 흘러가는가?

---

## 🚀 향후 로드맵 (Roadmap)

1. **gRPC 기반 통신 (RPC 전환)**: 텍스트 기반 JSON 통신을 이진(Binary) RPC로 교체하여 학습 속도를 5배 이상 추가 가속.
2. **Transformer 아키텍처**: 현재의 MLP 신경망을 기물 간의 관계를 파악하는 **Attention** 구조로 리뉴얼.
3. **대규모 Self-Play**: 15,000 에피소드 이상의 자기 대전을 통해 '알파고'급 전술 지능 확보.

---
**Maintained by Su-seok AI Engineer**
