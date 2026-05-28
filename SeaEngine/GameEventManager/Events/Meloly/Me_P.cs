using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Meloly;

[Event]
public class Me_P:IEvent
{
    public string Id => "Me_P";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if(data.ActivePlayer != card.Owner) return false;
        
        var enemyZone = card.Owner == data.Player1 ? 5 : 0;
        if (card.Unit.PosX != enemyZone) return true;
        
        var enemys = data.Board.Cards.Where(c => c.Unit.IsPlaced && c.Owner != card.Owner);
        foreach (var enemy in enemys)
        {
            enemy.Unit.GiveBuff("Infected", 2);
        }
        CombatUtils.Damage(card, 100, data);
        return true;
    }
}