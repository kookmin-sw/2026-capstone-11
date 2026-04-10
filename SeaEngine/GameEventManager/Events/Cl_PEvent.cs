using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Cl_PEvent : IEvent
{
    public string Id => "Cl_P";
    public string Timing => "TurnEnd";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        if (card.Owner != data.ActivePlayer || !card.Unit.IsPlaced) return;

        var inEnemyZone = (card.Owner == data.Player1 && card.Unit.PosX == 5) || (card.Owner == data.Player2 && card.Unit.PosX == 0);
        if (!inEnemyZone) return;

        var target = data.Board.Cards
            .Where(c => c.Owner != card.Owner && c.Unit.IsPlaced && c.Data.UnitType != UnitType.Leader)
            .OrderBy(c => c.Unit.Hp)
            .ThenBy(c => c.Unit.PosX)
            .ThenBy(c => c.Unit.PosY)
            .FirstOrDefault();
        if (target == null) return;

        target.Unit.Withdraw();
        card.Unit.Withdraw();
        data.UpdateResult();
    }
}
