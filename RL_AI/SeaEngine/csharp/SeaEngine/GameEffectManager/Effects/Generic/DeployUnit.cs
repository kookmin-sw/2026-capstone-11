using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class DeployUnit : IEffect
{
    public string Id => "DeployUnit";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var currentZone = card.Owner == data.Player1 ? Board.Player1Zone : Board.Player2Zone;

        return currentZone.Where(p => data.Board.IsEmptyCell(p.Item1, p.Item2))
            .Select(p => EffectTarget.Cell(p.Item1, p.Item2))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        data.GetCardById(source).Unit.Place(target.PosX, target.PosY);
        
        owner.Trash.AddCard(card);
    }
}