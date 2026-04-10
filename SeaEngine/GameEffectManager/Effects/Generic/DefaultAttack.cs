using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class DefaultAttack : IEffect
{
    public string Id => "DefaultAttack";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (!card.Unit.CanBasicAttack)
        {
            return [];
        }

        return data.GetAttackArea(card)
            .Where(p => !data.Board.IsEmptyCell(p.Item1, p.Item2) && data.Board.GetCardByPos(p.Item1, p.Item2)!.Owner != card.Owner)
            .Select(p => EffectTarget.Unit(data.Board.GetCardByPos(p.Item1, p.Item2)!.Guid))
            .ToList();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        var attacker = data.GetCardById(source);
        var defender = data.GetCardById(target.Guid);
        CombatUtils.Attack(attacker, defender, data);
        attacker.Unit.IsAttacked = true;
    }
}
