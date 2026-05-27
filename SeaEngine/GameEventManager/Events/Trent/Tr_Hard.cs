using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Trent;

[Event]
public class Tr_Hard : IEvent
{
    public string Id => "Tr_Hard";

    public string Timing => "Always";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (!card.Unit.IsMoved && !card.Unit.Buffs.ContainsKey("Hardened"))
        {
            card.Unit.Atk += 3;
            CombatUtils.GiveBuff(card, "Hardened", data);
            return true;
        }

        if (card.Unit.IsMoved && card.Unit.Buffs.ContainsKey("Hardened"))
        {
            card.Unit.Atk -= 3;
            CombatUtils.RemoveBuff(card, "Hardened", data);
            return true;
        }

        return false;
    }
}