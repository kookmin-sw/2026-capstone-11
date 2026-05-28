namespace SeaEngine.GameDataManager.Components.differences;

public class DifferenceLogger
{
    private List<Difference> _differences = [];
    private int _processedIndex = 0;
    public bool IsActivated = true;

    public void LogDifference(Difference difference)
    {
        if (!IsActivated) return;
        _differences.Add(difference);
    }

    public List<Difference> ProcessDifferences()
    {
        if (!IsActivated) return [];
        var differences = _differences[_processedIndex..];
        _processedIndex = _differences.Count;
        return differences;
    }
}