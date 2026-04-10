using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Cl_LEvent : IEvent
{
    public string Id => "Cl_L";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var hasKnightNearby = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .Any(c => c != null && c.Owner == card.Owner && c.Data.UnitType == UnitType.Knight);
        if (!hasKnightNearby) return;

        CombatUtils.Heal(card, 2, data);
    }
}
