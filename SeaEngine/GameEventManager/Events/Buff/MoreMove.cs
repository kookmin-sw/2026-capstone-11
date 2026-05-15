using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Buff;

[Event]
public class MoreMove : IEvent
{
    public string Id => "MoreMove";

    public string Timing => "Always";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);

        if (data.ActivePlayer != card.Owner)
        {
            card.Unit.RemoveBuff("MoreMove");
            return false;
        }

        if (!card.Unit.IsMoved) return false;
        card.Unit.IsMoved = false;
        card.Unit.RemoveBuff("MoreMove");
        return true;
    }
}