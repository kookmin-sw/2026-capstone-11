using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Meloly;

[Effect]
public class Me_L : IEffect
{
    public string Id => "Me_L";

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

        var enemys = data.Board.Cards.Where(c => c.Unit.IsPlaced && c.Owner != card.Owner);
        CombatUtils.Heal(card, enemys.Count() + 1, data);
        data.DrawCard(owner, 1);
        
        owner.Trash.AddCard(card);
    }
}