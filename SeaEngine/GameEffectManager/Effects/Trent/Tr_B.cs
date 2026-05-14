using System.ComponentModel.DataAnnotations;
using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Trent;

[Effect]
public class Tr_B : IEffect
{
    public string Id => "Tr_B";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.Board.Cards
            .Where(c => c.Unit.IsPlaced && c.Owner == card.Owner)
            .Select(c => EffectTarget.Unit(c.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var targetCard = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        var enemyZone = card.Owner == data.Player1 ? 5 : 0;
        if(targetCard.Unit.PosX != enemyZone) return;
        
        var dx = owner == data.Player1 ? 1 : -1;
        data.Board.MoveCard(targetCard, targetCard.Unit.PosX + dx, targetCard.Unit.PosY);
        
        owner.Trash.AddCard(card);
    }
}