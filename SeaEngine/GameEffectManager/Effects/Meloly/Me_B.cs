using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects.Meloly;

[Effect]
public class Me_B : IEffect
{
    public string Id => "Me_B";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        return data.GetMoveArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    private static List<(int, int)> _dir = [ (0, 1), (0, -1), (1, 0), (-1, 0) ];
    
    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var zone = data.GetCardZoneById(source);
        var card = data.GetCardById(source);
        var defender = data.GetCardById(target.Guid);
        var owner = card.Owner;
        
        zone.RemoveCard(card);

        CombatUtils.Attack(card, defender, data);
        foreach (var dir in _dir)
        {
            int x = dir.Item1 + card.Unit.PosX;
            int y = dir.Item2 + card.Unit.PosY;

            if (x is < 0 or >= Board.BoardSize || y is < 0 or >= Board.BoardSize) continue;
            if (data.Board.IsEmptyCell(x, y)) continue;
            
            var t = data.Board.GetCardByPos(x, y);
            if(t.Owner == card.Owner) continue;
            t.Unit.GiveBuff("Infected");
        }
        
        owner.Trash.AddCard(card);
    }
}