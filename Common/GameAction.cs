using SeaEngine.GameEffectManager;

namespace SeaEngine.Actions;

public record GameAction(string EffectId, Guid Source, EffectTarget Target)
{
    public readonly Guid Guid = Guid.NewGuid();
    public readonly string EffectId = EffectId;
    public readonly Guid Source = Source;
    public readonly EffectTarget Target = Target;
    
    public override string ToString() => $"{Guid} - {EffectId} - {Source} - {Target}";
}