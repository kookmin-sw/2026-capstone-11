using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Cl_R : IEffect
{
    //이동 범위 내 적을 하나 선택해 공격합니다.
    // 선택한 적 방향으로 한 칸 이동합니다.
    // 이동할 수 없었다면, 선택한 적에게 피해 1
    public string Id => "Cl_R"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        CombatUtils.Attack(card, data.GetCardById(target.Guid), data);
        //TODO : 미구현(보류)
        
        owner.Trash.AddCard(card);
    }
}