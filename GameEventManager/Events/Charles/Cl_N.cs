using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Charles;

[Event]
public class Cl_N : IEvent
{
    public string Id => "Cl_N";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        throw new NotImplementedException();
    }
}
