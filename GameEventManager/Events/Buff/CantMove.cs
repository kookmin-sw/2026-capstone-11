using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class CantMove : IEvent
{
    public string Id => "CantMove";

    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var unit = data.GetCardById(source).Unit;
        unit.IsMoved = true;
        unit.GiveBuff("CantMove", -1);
        if (unit.Buffs["CantMove"] == 0)
        {
            unit.RemoveBuff("CantMove");
        }
    }
}