using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_P : IEvent
{
    public string Id => "Or_P";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        throw new NotImplementedException();
    }
}
