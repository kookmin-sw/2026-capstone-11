using GoodServer.Game.Effects;

namespace GoodServer.Game.Phases.PhaseEffects.Effects;

[PhaseEffect(Phase.TurnEnd)]
public class TurnEnd : IEffect
{
    public string Description => "End Turn";

    public async Task Execute(IGameContext context)
    {
        if (context.TurnPlayer.Hand.Count > 4) //TODO : Remove Magic Number
        {
            var discards = 
                await context.InteractionContext.ChooseMultipleCard(context.TurnPlayer.Hand,
                context.TurnPlayer.Hand.Count - 4, context.TurnPlayer.Hand.Count - 4, context.TurnPlayer);
            if (discards == null) throw new Exception("No cards found in discard phase(client error?)");
            foreach (var discard in discards)
            {
                context.TurnPlayer.Discard(discard);
            }
        }

        context.SwitchTurnPlayer();
        context.Phase = Phase.TurnStart;
    }
}