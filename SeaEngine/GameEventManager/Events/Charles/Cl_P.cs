using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_P : IEvent
{
    //[턴 종료] Mistiltein :
    // 이 유닛이 상대편 영역에 있다면
    // 적 유닛 모두에게 2데미지를 주고
    // 이 유닛을 파괴합니다.
    
    public string Id => "Cl_P";
    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var enemyZone = card.Owner == data.Player1 ? 5 : 0;
        if (card.Unit.PosX == enemyZone)
        {
            foreach (var enemy in data.Board.Cards.Where(c => c.Owner != card.Owner))
            {
                if (enemy.Unit.IsPlaced) CombatUtils.Damage(enemy, 2, data);
            }
            CombatUtils.Damage(card, 100, data);
            return true;
        }
        return false;
    }
}
