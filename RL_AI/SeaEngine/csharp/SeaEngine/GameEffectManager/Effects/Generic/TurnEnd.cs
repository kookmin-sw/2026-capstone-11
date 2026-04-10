using SeaEngine.Common;
using SeaEngine.GameDataManager;

namespace SeaEngine.GameEffectManager.Effects;

[Effect]
public class TurnEnd : IEffect
{
    public string Id => "TurnEnd";

    public List<EffectTarget> GetTargets(Uid source, GameData data)
    {
        return [EffectTarget.None];
    }

    public void Apply(Uid source, EffectTarget target, GameData data)
    {
        data.ApplyTimedEvents("TurnEnd");
        data.DiscardDownTo(data.ActivePlayer, 3);
        data.TickStatuses();
        data.ActivePlayer = data.Player1 == data.ActivePlayer ? data.Player2 : data.Player1;
        data.Turn += 1;
        data.ResetMovementForTurn(data.ActivePlayer);
        data.DrawCard(data.ActivePlayer, 2);
        data.ApplyTimedEvents("TurnStart");
        data.UpdateResult();
    }
}
