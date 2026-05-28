using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class TempAtk : IEvent
{
    public string Id => "TempAtk";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        card.Unit.Atk -= card.Unit.Buffs["TempAtk"];
        CombatUtils.RemoveBuff(card, "TempAtk", data);
        return true;
    }
}