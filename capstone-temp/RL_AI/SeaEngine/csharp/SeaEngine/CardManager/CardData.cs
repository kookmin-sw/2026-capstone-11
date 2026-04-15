using SeaEngine.Common;

namespace SeaEngine.CardManager;

public record CardData(string Id, string Name, string LeaderId, UnitType UnitType, int Atk, int Hp, string? EffectId = null, string? EventId = null)
{
    public readonly string EffectId = EffectId ?? Id;
    public readonly string EventId = EventId ?? Id;
}