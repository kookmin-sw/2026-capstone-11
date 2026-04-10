using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Generic;

[Effect]
public class DefaultMove : IEffect
{
    public string Id => "DefaultMove";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var cur = data.Board.GetCardById(source);
        var targets = data.GetMoveArea(cur)
            .Where(v => data.Board.IsEmptyCell(v.Item1, v.Item2))
            .Select(v => EffectTarget.Cell(v.Item1, v.Item2)).ToList();
        return targets;
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var cur = data.Board.GetCardById(source);
        cur.Unit.Move(target.PosX, target.PosY);
        cur.Unit.IsMoved = true;
        
        data.TriggerEvent(cur.Data.EventId, "AfterMove", source);
    }
}