using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_R : IEvent
{
    //[턴 종료] 귤 발사:
    // 이 유닛이 이동 범위 내 적을 
    // 모두 공격합니다.
    public string Id => "Or_R";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var enemy = data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .ToList();

        foreach (var e in enemy)
        {
            if(e == null) continue;
            CombatUtils.Attack(card, e, data);
        }
    }
}
