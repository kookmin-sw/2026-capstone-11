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
        var unit = data.GetCardById(source).Unit;
        unit.GiveBuff("Infected", -1);
        if (unit.Buffs["Infected"] <= 0)
        {
            unit.RemoveBuff("Infected");
        }

        return true;
    }
}