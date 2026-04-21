using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_N : IEvent
{
    //[턴 시작] Eisritterin:
    // 아군 군주의 이동 범위 안에 있으면
    // 이번 턴 끝까지 공격력 + 1 
    
    public string Id => "Cl_N";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var card = data.Board.GetCardById(source);
        var leader = data.Board.Cards
            .First(c => c.Owner == data.GetCardById(source).Owner && c.Data.UnitType == UnitType.Leader);
        
        
        if (data.GetMoveArea(leader)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) &&
                        data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner == card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .Any(p => p == card))
        {
            card.Unit.Atk += 1;
            card.Unit.GiveBuff("TempAtk", 1);
        }
    }
}
