using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Or_B : IEffect
{
    //아군 리더를 이 유닛의 이동범위 안 원하는 곳으로 이동시킵니다.
    public string Id => "Or_B"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        //킹이 살아있지 않은 경우는 고려할 필요가 없음.
        return data.GetMoveArea(data.GetCardById(source))
            .Where(p => data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => EffectTarget.Cell(p.Item1, p.Item2))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        data.Board.Cards
            .First(c => c.Owner == data.GetCardById(source).Owner && c.Data.UnitType == UnitType.Leader)
            .Unit.Move(target.PosX, target.PosY);
        
        owner.Trash.AddCard(card);
    }
}