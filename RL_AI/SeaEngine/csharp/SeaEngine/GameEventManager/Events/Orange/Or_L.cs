using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_L : IEvent
{
    //[턴 종료] 귤 먹기 :
    // 자신 체력을 1 회복합니다
    public string Id => "Or_L";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        CombatUtils.Heal(data.GetCardById(source), 1, data);
    }
}
