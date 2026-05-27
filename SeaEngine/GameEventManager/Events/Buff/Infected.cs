using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class Infected : IEvent
{
    public string Id => "Infected";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        CombatUtils.GiveBuff(card, "Infected", data, -1);
        if (card.Unit.Buffs["Infected"] <= 0)
        {
            CombatUtils.RemoveBuff(card, "Infected", data);
        }

        return true;
    }
}