using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;
using SeaEngine.Logger;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Cl_B : IEffect
{
    //이동범위 안에 유닛이 3기 이상 존재한다면 공격력 +1을 얻습니다.
    //이동범위 내 적을 모두 공격합니다.
    public string Id => "Cl_B"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return [EffectTarget.None];
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        var enemy = data.GetMoveArea(card)
            .Where(p => data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => data.Board.GetCardByPos(p.Item1, p.Item2))
            .ToList();
        if (enemy.Count >= 3)
        {
            //TODO : 버프 구현
        }
        foreach (var e in enemy)
        {
            if (e == null) continue;
            CombatUtils.Attack(card, e, data);
        }
        
        owner.Trash.AddCard(card);
    }
}