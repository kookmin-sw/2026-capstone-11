using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_L : IEvent
{
    //[턴 시작] Eisprinzessin :
    // 이동 범위 안에 아군 나이트가 있으면 자신 체력을 2 회복합니다
    public string Id => "Cl_L";
    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) &&
                        data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner == card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .Any(p => p?.Data.UnitType == UnitType.Knight))
        {
            CombatUtils.Heal(card, 2, data);
            return true;
        }

        return false;
    }
}
