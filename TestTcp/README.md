## 서버 실행
```
dotnet run --project ./Game.Server/Game.Server.csproj
```

## 서버 빌드
```
dotnet build ./Game.Server/Game.Server.csproj -c Debug
```

## 네트워크 DLL 빌드 및 Unity 적용
```
dotnet build ./Game.Network/Game.Network.csproj
```
위 DLL 빌드 후, `TestTcp/Game.Network/Game.Network/bin/Debug/netstandard2.1/Game.Network.dll` 파일을 `UnityChess/Assets/Plugins` 폴더로 옮겨서 사용합니다. 

해당 dll 파일은 깃 버전 관리 대상이 아닙니다. 
리포지토리 복제 후, dll 파일을 빌드해 적용하는 것을 원칙으로 합니다.

해당 dll 적용 이전에 유니티 실행시 dll과 유니티 파일간 의존성 문제가 발생할 수 있습니다. 유니티 실행 전, 먼저 적용하시길 권장합니다.



