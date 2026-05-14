using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Trent;

[Effect]
public class Tr_R : IEffect
{
    
    public string Id => "Tr_R"; 

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (!card.Unit.IsMoved) return [];
        
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

        card.Unit.IsMoved = true;
        data.GetCardById(target.Guid).Unit.GiveBuff("CantMove", 1);
        
        owner.Trash.AddCard(card);
    }
}