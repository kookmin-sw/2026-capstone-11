using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class TempAtk : IEvent
{
    public string Id => "TempAtk";

    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var cur = data.GetCardById(source).Unit;
        cur.Atk -= cur.Buffs["TempAtk"];
        cur.RemoveBuff("TempAtk");
    }
}