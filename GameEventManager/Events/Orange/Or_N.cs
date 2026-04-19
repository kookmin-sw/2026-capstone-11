using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_N : IEvent
{
    //[파괴 시] 망상 전파 :
    // 이동 범위 내 모든 적 유닛에게
    // 2피해를 줍니다.
    public string Id => "Or_N";
    public string Timing => "OnDestroy";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        
        var enemy = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .ToList();
        
        foreach (Card? e in enemy)
        {
            if(e.Unit.Hp <= 0) continue;
            CombatUtils.Damage(e, 2, data);
        }
        return true;
    }
}
