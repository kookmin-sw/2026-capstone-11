using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Cl_BEvent : IEvent
{
    public string Id => "Cl_B";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var hasLeaderNearby = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .Any(c => c != null && c.Owner == card.Owner && c.Data.UnitType == UnitType.Leader);
        if (!hasLeaderNearby) return;

        card.Unit.AddOrRefreshStatus(UnitStatusType.AttackModifier, 1, 1, $"event:{Id}");
    }
}
