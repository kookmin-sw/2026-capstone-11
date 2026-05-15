using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Rule;

[Event]
public class RuleTurnStart : IEvent
{
    public string Id => "Rule";
    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        data.DrawCard(data.ActivePlayer, data.TurnCnt == 0 ? 1 : 3);
        
        var myUnits = data.Board.Cards.Where(c => c.Owner == data.ActivePlayer);
        return true;
    }
}
