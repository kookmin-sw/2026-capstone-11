using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Meloly;

[Event]
public class Me_L : IEvent
{
    public string Id =>  "Me_L"; 

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if(data.ActivePlayer != card.Owner) return false;
        foreach (var target in data.Board.Cards.Where((c => c.Unit.Buffs.ContainsKey("Infected"))))
        {
            CombatUtils.Damage(target, 1, data);
        }
        return true;
    }
}