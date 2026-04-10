using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Or_REvent : IEvent
{
    public string Id => "Or_R";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var target = data.GetAttackArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .FirstOrDefault(c => c != null && c.Owner != card.Owner);
        if (target == null) return;

        CombatUtils.Attack(card, target, data);
    }
}
