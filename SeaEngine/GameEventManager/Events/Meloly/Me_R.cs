using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Meloly;

[Event]
public class Me_R : IEvent
{
    public string Id => "Me_R";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if(data.ActivePlayer != card.Owner) return false;
        var enemy = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .ToList();
        if (!enemy.Any(c => c.Unit.Buffs.ContainsKey("Infected"))) return false;
        
        CombatUtils.Damage(card, 1, data);
        return true;
    }
}