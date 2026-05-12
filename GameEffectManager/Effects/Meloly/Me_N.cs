using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Meloly;

[Effect]
public class Me_N : IEffect
{
    public string Id => "Me_N";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var targetCard = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);
        
        data.Board.SwapCards(card, targetCard);
        if(targetCard.Owner != owner) targetCard.Unit.GiveBuff("Infected");
        
        owner.Trash.AddCard(card);
    }
}