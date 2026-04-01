using SeaEngine.Actions;
using SeaEngine.CardManager;
using SeaEngine.GameDataManager;
using SeaEngine.Logger;

namespace SeaEngine;

public partial class Game(CardLoader cardLoader, ILogger logger, string player1Id, string player2Id)
{
    public readonly CardLoader CardLoader = cardLoader;
    public readonly GameData Data = new GameData(player1Id, player2Id);
    public readonly ILogger Logger = logger;
    private List<GameAction> _actions = [];
    public IReadOnlyList<GameAction> Actions => _actions;
    
    public override string ToString()
    {
        return $@"
{Data}

Actions:
{string.Join("\n", _actions)}
";
    }
}