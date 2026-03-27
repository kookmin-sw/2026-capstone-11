using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class DefaultMove : IEffect
{
    public string Id => "DefaultMove";

    public List<EffectTarget> GetTargets(Guid source, GameData data)
    {
        var cur = data.Board.GetCardById(source);
        var targets = data.GetMoveArea(cur)
            .Where(v => data.Board.IsEmptyCell(v.Item1, v.Item2))
            .Select(v => EffectTarget.Cell(v.Item1, v.Item2)).ToList();
        return targets;
    }

    public void Apply(Guid source, EffectTarget target, GameData data)
    {
        //유효성 검사는 필요없음. GetTarget가 해줌.
        var cur = data.Board.GetCardById(source);
        cur.Unit.Move(target.PosX, target.PosY);
        cur.Unit.IsMoved = true;
        
        //TODO : 일반 이동 시 일어나는 이벤트 호출해야 함.
    }
}