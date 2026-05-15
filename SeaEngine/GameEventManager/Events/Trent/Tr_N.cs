using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Trent;

[Event]
public class Tr_N : IEvent
{
    public string Id => "Tr_N";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if(data.ActivePlayer != card.Owner) return false;

        if (card.Unit.IsMoved) return false;
        
        var enemy = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .ToList();

        foreach (var e in enemy)
        {
            CombatUtils.Attack(card, e, data);
        }
        return true;
    }
}