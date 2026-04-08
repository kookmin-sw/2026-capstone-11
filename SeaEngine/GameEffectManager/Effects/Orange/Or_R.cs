using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Or_R : IEffect
{
    // 이 유닛이 이동하지 않았다면, 이동범위 내 적을 하나 선택합니다.
    // 선택한 유닛과 이 유닛은 다음 상대 턴 종료까지 이동할 수 없습니다.
    public string Id => "Or_R"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Unit.IsMoved) return [];
        
        return data.GetMoveArea(card)
            .Where(p => data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        //TODO: 미구현, 버프 구현 이후에 구현
        
        owner.Trash.AddCard(card);
    }
}