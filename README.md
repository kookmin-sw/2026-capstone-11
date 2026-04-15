# Call of the King: RL_AI (SeaEngine)

`RL_AI`는 C# 게임 엔진 `SeaEngine`을 Python 강화학습 루프에 연결해, 대량 self-play 로그를 쌓고 밸런싱 분석에 활용하는 프로젝트입니다.

---

## 현재 코드 기준 아키텍처

```text
start.ipynb
  -> experiment.py (실험 전체 흐름, 체크포인트, 평가, 리포트/압축)
  -> trainer.py (PPO 학습 루프)
  -> bridge/vector_env.py (병렬 env 관리)
  -> bridge/pythonnet_session.py (C# DLL in-process 호출, PythonNet)
  -> csharp/SeaEngine (핵심 게임 로직)
```

- 기본 브리지 경로는 `PythonNet + DLL 직접 호출`입니다.
- `VectorSeaEngineEnv`는 `local` 백엔드 기준 다중 세션 병렬 실행을 지원합니다.
- 정책 추론은 배치(`compute_policy_output_batch`)로 처리합니다.

---

## 최근 핵심 변경 요약

### 1) 안정성/실행 환경
- `start.ipynb`에서 압축 해제/실행 흐름을 정리하고, 실험 재실행 시 모듈 캐시를 정리하도록 반영.
- C# DLL 경로 해석을 `Release/Debug` 모두 대응하도록 보강.
- `Uid` 처리 및 액션 적용 경로를 정리해 `Guid` 포맷 오류를 제거.
- `RlObservationExporter`에서 중복 key 예외(`An item with the same key...`)가 나지 않도록 방어 로직 추가.

### 2) 로그/출력 정리
- 과도한 매치 단위 출력 제거, 핵심 진행 로그(heartbeat/200ep 요약/checkpoint) 중심으로 정리.
- 체크포인트 평가는 `greedy` 기준 8조합(`덱 2 x 선후공 2 x 같은/다른 덱 2`), 조합당 50판(총 400판)으로 통일.
- 체크포인트마다 조합별 `history` 텍스트를 별도 파일로 저장.

### 3) 학습 구조 개선
- `train_max_turns=100` 기본화(학습 horizon 확장).
- `SeaEngineRLAgent`가 `device=auto`를 지원하며 CUDA 가능 시 GPU 사용.
- Dense reward shaping 추가:
  - 리더 HP 변화
  - 보드 점유 변화
  - 행동 타입(attack/deploy/turn end) 기반 작은 밀집 보상
  - terminal reward와 누적 결합
- 커리큘럼 스케줄 추가:
  - 초반: random 중심
  - 중반: random + greedy
  - 후반: random + greedy + self_ep_*

### 4) 산출물 관리
- 실험 완료 시 이번 실행에서 생성된 `log/*.txt` 자동 zip 압축.
- 실험 완료 시 이번 실행에서 생성된 `models/*.pt` 자동 zip 압축.
- 반환값에 `log_zip_path`, `model_zip_path` 포함.

---

## 체크포인트/평가 정책 (현재)

- 기본 학습: `10000` episodes
- 학습 chunk: `1000` episodes
- 매 chunk 종료 시 checkpoint 평가:
  - 상대: `greedy`
  - 축: `귤/샤를로테`, `선공/후공`, `같은 덱/다른 덱`
  - 조합: 8개
  - 조합당 50판, 총 400판
- 최종 전/후 평가:
  - `vs random` 50판
  - `vs greedy` 50판

---

## 최근 실험 결과 요약 (2026-04-15 실행 로그 기준)

- Before training:
  - vs random: `0%`
  - vs greedy: `0%`
- After training:
  - vs random: `86%`
  - vs greedy: `60%`
- 해석:
  - 초기 대비 실력은 큰 폭으로 개선.
  - 다만 체크포인트별 성능 변동성이 남아 있어, 안정 수렴 개선이 다음 과제.

---

## 현재 남은 과제

1. `self_ep_n`별 성능을 직접 집계하는 로그/리포트 확장  
2. 커리큘럼 비율(특히 3000~7000 구간) 안정화  
3. 병렬 설정(`local_threads`, `num_envs`) 실측 기반 튜닝  
4. 체크포인트 history 기반 전술 패턴(콤보/자원 아끼기/마무리 타이밍) 분석 자동화
