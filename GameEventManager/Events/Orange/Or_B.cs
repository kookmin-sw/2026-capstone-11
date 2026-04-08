using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Orange;

[Event]
public class Or_B : IEvent
{
    public string Id => "Or_B";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        throw new NotImplementedException();
    }
}
