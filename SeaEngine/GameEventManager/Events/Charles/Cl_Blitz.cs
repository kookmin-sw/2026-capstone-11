using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_Blitz : IEvent
{
    //[턴 시작] Blitzschwert :
    // 이동 범위 안에 아군 군주가 있으면 
    // 이번 턴 끝까지 공격력 + 1
    public string Id => "Cl_Blitz";
    public string Timing => "TurnStart";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) &&
                        data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner == card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .Any(p => p?.Data.UnitType == UnitType.Leader))
        {
            card.Unit.Atk += 1;
            card.Unit.GiveBuff("TempAtk", 1);
            return true;
        }
        return false;
    }
}
