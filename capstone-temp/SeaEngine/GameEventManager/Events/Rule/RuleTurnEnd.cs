using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Rule;

[Event]
public class RuleTurnEnd : IEvent
{
    public string Id => "Rule";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
    }
}
