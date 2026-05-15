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
        LastActionData = null;
    }
    
    public override string ToString()
    {
        return $@"
{Data}

Actions:
{string.Join("\n", Actions)}
";
    }

    private static readonly JsonConverter[] SerializeConverters =
    [
        new CardZoneConverter(),
        new CardConverter(),
        new BoardConverter(),
        new ActionConverter(),
        new TargetConverter()
    ];

    public string Serialize()
    {
        return JsonConvert.SerializeObject(this, Formatting.Indented, SerializeConverters);
    }
}