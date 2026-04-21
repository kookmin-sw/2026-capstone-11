using SeaEngine.GameEffectManager;

namespace SeaEngine.Common;

public record GameAction(string EffectId, Uid Source, EffectTarget Target)
{
    public readonly Uid Guid = new Uid("A");
    public readonly string EffectId = EffectId;
    public readonly Uid Source = Source;
    public readonly EffectTarget Target = Target;
    
    public override string ToString() => $"{Guid} - {EffectId} - {Source} - {Target}";
}