using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Trent;

[Effect]
public class Tr_N : IEffect
{
    public string Id => "Tr_N";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.Board.Cards.Where(c => 
                c.Owner == card.Owner && 
                c.Unit.IsPlaced && 
                c.Data.UnitType != UnitType.Leader && 
                c != card)
            .Select(c => EffectTarget.Unit(c.Guid)).ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        var targetCard = data.GetCardById(target.Guid);
        var targetCardZone = data.GetCardZoneById(target.Guid);
        CombatUtils.Damage(targetCard, 100, data);
        targetCardZone.RemoveCard(targetCard);
        owner.Hand.AddCard(targetCard);
        
        
        owner.Trash.AddCard(card);
        
    }
}