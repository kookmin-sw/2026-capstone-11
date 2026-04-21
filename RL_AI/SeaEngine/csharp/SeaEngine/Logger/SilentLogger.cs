using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.Logger;

public class SilentLogger : ILogger
{
    public void Log(string message, GameAction action, GameData data)
    {
        // Do nothing to be silent and fast
    }
}
