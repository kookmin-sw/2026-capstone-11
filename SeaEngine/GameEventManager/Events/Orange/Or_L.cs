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

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if(data.ActivePlayer != card.Owner) return false;
        
        CombatUtils.Heal(card, 1, data);
        return true;
    }
}
