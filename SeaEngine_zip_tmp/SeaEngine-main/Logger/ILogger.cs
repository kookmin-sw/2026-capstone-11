using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.Logger;

public interface ILogger
{
    void Log(string message, GameAction action, GameData data);
    //일단 string으로 남기자... 구조를 지금 Fix하는 데 너무 큰 비용이 들어요.
}