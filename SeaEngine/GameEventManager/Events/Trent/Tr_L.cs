using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEventManager.Events.Trent;

[Event]
public class Tr_L : IEvent
{
    public string Id => "Tr_L";

    public string Timing => "TurnEnd";

    public bool Apply(Uid source, GameData data)
    {
        var card = data.GetCardById(source);
        foreach (var target in data.Board.Cards.Where(c =>
                     c.Owner == card.Owner && c.Unit is { IsPlaced: true, IsMoved: false }))
        {
            CombatUtils.Heal(target, 2, data);
        }
        return true;
    }
}