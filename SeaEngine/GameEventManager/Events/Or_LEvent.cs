using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Or_LEvent : IEvent
{
    public string Id => "Or_L";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;
        CombatUtils.Heal(card, 1, data);
    }
}
