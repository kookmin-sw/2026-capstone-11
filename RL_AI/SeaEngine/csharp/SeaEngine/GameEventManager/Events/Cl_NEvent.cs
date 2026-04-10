using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Cl_NEvent : IEvent
{
    public string Id => "Cl_N";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var leader = data.GetLeader(card.Owner);
        if (leader == null || !leader.Unit.IsPlaced) return;
        var leaderThreatensCard = data.GetMoveArea(leader).Any(p => p == (card.Unit.PosX, card.Unit.PosY));
        if (!leaderThreatensCard) return;

        card.Unit.AddOrRefreshStatus(UnitStatusType.AttackModifier, 1, 1, $"event:{Id}");
    }
}
