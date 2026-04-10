using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects;

public class Blank : IEffect
{
    public string Id => "Er_L";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return new List<EffectTarget>();
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        return;
    }
}