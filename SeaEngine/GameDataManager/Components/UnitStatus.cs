namespace SeaEngine.GameDataManager.Components;

public class UnitStatus(UnitStatusType type, int value, int remainingTurns, string sourceKey)
{
    public UnitStatusType Type { get; } = type;
    public int Value { get; private set; } = value;
    public int RemainingTurns { get; private set; } = remainingTurns;
    public string SourceKey { get; } = sourceKey;

    public void Refresh(int value, int remainingTurns)
    {
        Value = value;
        RemainingTurns = remainingTurns;
    }

    public bool Tick()
    {
        if (RemainingTurns > 0)
        {
            RemainingTurns -= 1;
        }
        return RemainingTurns <= 0;
    }
}
