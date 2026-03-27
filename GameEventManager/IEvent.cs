using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager;

public interface IEvent
{
    public string Id { get; }
    public string Timing { get; }
    public void Apply(Guid source, GameData data);
}