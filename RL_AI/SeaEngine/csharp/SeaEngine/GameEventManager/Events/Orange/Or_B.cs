using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_B : IEvent
{
    //[파괴 시] 망상 강화 :
    // 내 군주의 체력을 2 회복합니다
    
    public string Id => "Or_B";
    public string Timing => "OnDestroy";

    public void Apply(Uid source, GameData data)
    {
        var leader = data.Board.Cards
            .First(c => c.Owner == data.GetCardById(source).Owner && c.Data.UnitType == UnitType.Leader);
        CombatUtils.Heal(leader, 2, data);
    }
}
