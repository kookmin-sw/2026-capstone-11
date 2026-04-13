using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Charles;

[Effect]
// ReSharper disable once InconsistentNaming
public class Cl_L : IEffect
{
    //카드를 한 장 뽑습니다. 이동범위 내 아군을 선택해 체력을 3 회복시킵니다.
    public string Id => "Cl_L"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) 
                        && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner == data.GetCardById(source).Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        CombatUtils.Heal(data.GetCardById(target.Guid), 3, data);
        data.DrawCard(owner, 1);
        
        owner.Trash.AddCard(card);
    }
}