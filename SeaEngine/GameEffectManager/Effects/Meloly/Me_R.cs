using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Meloly;

[Effect]
public class Me_R : IEffect
{
    public string Id => "Me_R";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.Board.Cards.Where(c => c.Owner != card.Owner).Select(c => EffectTarget.Unit(c.Guid)).ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var targetCard = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        var enemys = data.Board.Cards.Where(c => c.Unit.IsPlaced && c.Owner != card.Owner);
        CombatUtils.Damage(targetCard, enemys.Count(), data);
        data.DrawCard(owner, 1);
        
        owner.Trash.AddCard(card);
    }
}