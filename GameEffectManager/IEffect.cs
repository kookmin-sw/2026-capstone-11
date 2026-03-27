using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager;

public interface IEffect
{
    public string Id { get; }
    public List<EffectTarget> GetTargets(Guid source, GameData data);
    public void Apply(Guid source, EffectTarget target, GameData data);
}