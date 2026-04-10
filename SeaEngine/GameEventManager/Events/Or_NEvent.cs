using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events;

[Event]
public class Or_NEvent : IEvent
{
    public string Id => "Or_N";
    public string Timing => "OnDestroyed";

    public void Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        var target = data.Board.Cards
            .Where(c => c.Owner != card.Owner && c.Unit.IsPlaced)
            .OrderBy(c => c.Unit.Hp)
            .ThenBy(c => c.Unit.PosX)
            .ThenBy(c => c.Unit.PosY)
            .FirstOrDefault();
        if (target == null) return;

        target.Unit.Hp -= 2;
        if (target.Unit.Hp <= 0)
        {
            target.Unit.Withdraw();
            data.UpdateResult();
        }
    }
}
