using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.Logger;

public class SimpleLogger : ILogger
{
    public void Log(string message, GameAction action, GameData data)
    {
        Console.WriteLine($"{message}");
    }
}