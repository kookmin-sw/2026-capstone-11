using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Rule;

[Event]
public class RuleTurnStart : IEvent
{
    public string Id => "Rule";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        data.DrawCard(data.ActivePlayer, 3);
        
        if (data.TurnCnt == 0) return;
        
        var myUnits = data.Board.Cards.Where(c => c.Owner == data.ActivePlayer);
        foreach (var unit in myUnits)
        {
            unit.Unit.IsMoved = false;
        }
    }
}
