using SeaEngine.GameEffectManager;

namespace SeaEngine.Common;

public class GameAction(string effectId, Uid source, EffectTarget target, UidFactory uidFactory)
{
    public readonly Uid Guid = uidFactory.Next();
    public readonly string EffectId = effectId;
    public readonly Uid Source = source;
    public readonly EffectTarget Target = target;
    
    public override string ToString() => $"{Guid} - {EffectId} - {Source} - {Target}";
}