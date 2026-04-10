using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Or_PEvent : IEvent
{
    public string Id => "Or_P";
    public string Timing => "TurnStart";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var inEnemyZone = (card.Owner == data.Player1 && card.Unit.PosX == 5) || (card.Owner == data.Player2 && card.Unit.PosX == 0);
        if (!inEnemyZone) return;
        data.DrawCard(card.Owner, 1);
    }
}
