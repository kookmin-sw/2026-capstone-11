using Newtonsoft.Json;
using SeaEngine.CardManager;
using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Converters;
using SeaEngine.Logger;

namespace SeaEngine;

public partial class Game(CardLoader cardLoader, ILogger logger, string player1Id, string player2Id)
{
    [JsonIgnore]
    public readonly CardLoader CardLoader = cardLoader;
    public GameData Data { get; private set; } = new GameData(player1Id, player2Id, logger);
    [JsonIgnore]
    public readonly ILogger Logger = logger;
    private List<GameAction> _actions = [];
    public IReadOnlyList<GameAction> Actions => _actions;

    public void SetData(GameData gameData)
    {
        Data = gameData;
        UpdateActions();
    }

    public Game Fork()
    {
        var fork = new Game(CardLoader, Logger, Data.Player1.Id, Data.Player2.Id);
        fork.SetData(Data.Clone());
        return fork;
    }

    public Game Clone() => Fork();
    
    public override string ToString()
    {
        return $@"
{Data}

Actions:
{string.Join("\n", Actions)}
";
    }

    public string Serialize()
    {
        return JsonConvert.SerializeObject(this, Formatting.Indented, [
            new CardZoneConverter(),
            new CardConverter(),
            new BoardConverter(),
            new ActionConverter(),
            new TargetConverter()
        ]);
    }
}
