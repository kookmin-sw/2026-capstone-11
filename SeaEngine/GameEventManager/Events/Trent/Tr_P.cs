using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Trent;

[Event]
public class Tr_P : IEvent
{
    public string Id => "Tr_P";

    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        
        var enemyZone = card.Owner == data.Player1 ? 5 : 0;
        if(card.Unit.PosX != enemyZone) return false;
        
        foreach (var c in data.Board.Cards)
        {
            if(c.Owner != card.Owner) continue;
            if(!c.Unit.IsPlaced) continue;
            
            c.Unit.GiveBuff("MoreMove");
        }
        return true;
    }
}