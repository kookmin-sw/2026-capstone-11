using SeaEngine.GameEffectManager;

namespace SeaEngine.GameDataManager.Components.differences;

public record Difference(string Name, List<EffectTarget> Targets);