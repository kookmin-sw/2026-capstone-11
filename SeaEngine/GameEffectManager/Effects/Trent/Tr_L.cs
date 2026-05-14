using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Trent;

[Effect]
public class Tr_L : IEffect
{
    public string Id => "Tr_L";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.Board.Cards.Where(c => c.Owner == card.Owner && c.Unit.IsPlaced && c.Unit.IsMoved == true)
            .Select(c => EffectTarget.Unit(c.Guid)).ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var targetCard = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        targetCard.Unit.Atk += 2;
        targetCard.Unit.GiveBuff("TempAtk", 2);
        data.DrawCard(owner, 1);
        
        owner.Trash.AddCard(card);
        
    }
}