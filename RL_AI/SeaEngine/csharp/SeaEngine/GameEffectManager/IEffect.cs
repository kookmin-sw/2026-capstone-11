using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager;

public interface IEffect
{
    public string Id { get; }
    public List<EffectTarget> GetTargets(Uid source, GameData data);
    public void Apply(Uid source, EffectTarget target, GameData data);
}