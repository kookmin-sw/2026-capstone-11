using SeaEngine.GameDataManager;
using SeaEngine.Common;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Or_BEvent : IEvent
{
    public string Id => "Or_B";
    public string Timing => "OnDestroyed";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var leader = data.GetLeader(card.Owner);
        if (leader == null || !leader.Unit.IsPlaced) return;
        CombatUtils.Heal(leader, 2, data);
    }
}
