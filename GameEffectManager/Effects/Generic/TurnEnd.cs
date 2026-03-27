using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class TurnEnd : IEffect
{
    public string Id => "TurnEnd";

    public List<EffectTarget> GetTargets(Guid source, GameData data)
    {
        throw new NotImplementedException();
    }

    public void Apply(Guid source, EffectTarget target, GameData data)
    {
        throw new NotImplementedException();
    }
}