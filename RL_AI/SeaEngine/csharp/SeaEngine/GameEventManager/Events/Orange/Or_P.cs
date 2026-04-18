using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_P : IEvent
{
    //[턴 종료] 요정의 영토 :
    // 이 유닛이 상대편 영역에 있다면
    // 카드를 한 장 뽑습니다
    
    public string Id => "Or_P";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var enemyZone = card.Owner == data.Player1 ? 5 : 0;
        if(card.Unit.PosX == enemyZone) data.DrawCard(card.Owner, 1);
    }
}
