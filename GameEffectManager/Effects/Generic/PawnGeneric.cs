using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Generic;

[Effect]
public class PawnGeneric : IEffect
{
    public string Id => "PawnGeneric";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return data.Board.Cards.Where(u => u.Unit.IsPlaced && u.Owner == data.GetCardById(source).Owner)
            .Aggregate(new List<EffectTarget>(), 
                (current, card) => (current.Concat(data.GetMoveArea(card)
                    .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != data.GetCardById(source).Owner)
                    .Select(v => EffectTarget.Unit2(card.Guid, data.Board.GetCardByPos(v.Item1, v.Item2)!.Guid))
                    ))
                .ToList());
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        var attacker = data.GetCardById(target.Guid);
        var defender = data.GetCardById(target.Guid2);
        
        CombatUtils.Attack(attacker, defender, data);
        
        owner.Trash.AddCard(card);
    }
}