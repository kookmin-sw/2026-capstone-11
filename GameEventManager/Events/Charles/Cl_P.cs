using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_P : IEvent
{
    public string Id => "Cl_P";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        throw new NotImplementedException();
    }
}
