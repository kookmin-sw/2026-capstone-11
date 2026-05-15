using GoodServer.Game.Effects;

namespace GoodServer.Game.Phases.PhaseEffects.Effects;

[PhaseEffect(Phase.PreGame)]
public class TurnStart : IEffect
{
    public string Description => "Turn Start";

    public async Task Execute(IGameContext context)
    {
        int drawAmount = 3 - context.TurnPlayer.Hand.Count;
        context.TurnPlayer.Draw(drawAmount);
        context.Phase = Phase.Turn;
    }
}