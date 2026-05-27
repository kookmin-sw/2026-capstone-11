using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class CantMove : IEvent
{
    public string Id => "CantMove";

    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        card.Unit.IsMoved = true;
        CombatUtils.GiveBuff(card, "CantMove", data, -1);
        if (card.Unit.Buffs["CantMove"] <= 0)
        {
            CombatUtils.RemoveBuff(card, "CantMove", data);
        }

        return true;
    }
}