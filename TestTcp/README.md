## 서버 실행
```
dotnet run --project ./Game.Server/Game.Server.csproj
```

## 서버 빌드
```
dotnet build ./Game.Server/Game.Server.csproj -c Debug
```

## 네트워크 DLL 빌드
```
dotnet build ./Game.Network/Game.Network.csproj
```
위 DLL 빌드 후, `./Game.Network/Game.Network/bin/Debug/netstandard2.1/Game.Network.dll` 파일 사용



