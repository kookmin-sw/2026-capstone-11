# Game.Client — Network Test Client

## 실행

```bash
dotnet run
```

## 모드 선택

| 입력 | 설명 |
|------|------|
| `s`  | 서버 모드 — 포트 9000 리슨, 클라이언트 에코 응답 |
| `c`  | 클라이언트 모드 — 원격 서버(127.0.0.1:9000)에 다중 접속 |
| `t`  | 로컬 자동 테스트 — 같은 프로세스 내 서버+클라이언트 |

## 파라미터 변경

`Program.cs` 상단 `TestConfig` 상수 수정:

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `ServerPort` | 9000 | 포트 |
| `ClientCount` | 3 | 동시 접속 클라이언트 수 |
| `MsgPerClient` | 20 | 클라이언트 당 전송 메세지 수 (0=무제한) |
| `MsgSizeBytes` | 64 | 메세지 크기 (bytes) |
| `MsgIntervalMs` | 500 | 전송 빈도 (0=최대속도) |
| `QueryTimeoutMs` | 3000 | 쿼리 응답 타임아웃 |

## 서버+클라이언트 분리 실행

```bash
# 터미널 1 — 서버
dotnet run
> s

# 터미널 2 — 클라이언트
dotnet run
> c
```
