using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.Logger;

public interface ILogger
{
    void LogAction(GameAction action, GameData data);
    void LogCards(GameData data);
    void Log(string message, GameData data);
}