using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects.Generic;

[Effect]
public class ER_L : IEffect
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