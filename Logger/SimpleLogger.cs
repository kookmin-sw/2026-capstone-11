using System.Text;
using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.Logger;

public class SimpleLogger : ILogger
{
    private readonly StringBuilder _builder = new StringBuilder();
    public string GameId { get; }
    public SimpleLogger(string gameId)
    {
        GameId = gameId;
        _builder.AppendLine($"{gameId} : game Started");
    }

    public void LogCards(GameData data)
    {
        foreach (var card in data.Board.Cards)
        {
            _builder.AppendLine(card.ToString());
        }
    }
    public void Log(string message, GameData data)
    {
        _builder.AppendLine($"{message}");
    }
    
    public void LogAction(GameAction action, GameData data)
    {
        _builder.AppendLine($"useAction({action.Guid}, {action.EffectId}) / {action.Source} -> {action.Target}");
    }

    public string EndLogging()
    {
        _builder.AppendLine($"{GameId} : game Ended");
        return _builder.ToString();
    }
}