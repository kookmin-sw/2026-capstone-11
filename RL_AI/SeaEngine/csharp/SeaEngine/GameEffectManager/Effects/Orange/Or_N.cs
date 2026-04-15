using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Orange;

[Effect]
// ReSharper disable once InconsistentNaming
public class Or_N : IEffect
{
    //이동범위 내 적을 하나 선택해 공격합니다. 적 유닛이 이 공격으로 파괴되었다면, 이동 범위 내 모든 적을 공격합니다.
    public string Id => "Or_N"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return data.GetMoveArea(data.GetCardById(source))
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && 
                        data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != data.GetCardById(source).Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        if (CombatUtils.Attack(card, data.GetCardById(target.Guid), data))
        {
            var enemy = data.GetMoveArea(data.GetCardById(source))
                .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2))
                .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
                .Where(p => p!.Owner != owner);
            foreach (var e in enemy)
            {
                if (e == null) continue;
                CombatUtils.Attack(card, e,  data);
            }
        }
        
        owner.Trash.AddCard(card);
    }
}