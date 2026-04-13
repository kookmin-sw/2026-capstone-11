using GoodServer.Game.Effects;

namespace GoodServer.Game.Phases.PhaseEffects.Effects;

[PhaseEffect(Phase.PreGame)]
public class PreGame : IEffect
{
    public string Description => "Initialize Game";

    public async Task Execute(IGameContext context)
    {
        context.GameData.Player1.SetDeck(await context.InteractionContext.GetDeck(context.GameData.Player1));
        context.GameData.Player2.SetDeck(await context.InteractionContext.GetDeck(context.GameData.Player2));

        context.GameData.Player1.Draw(3);
        context.GameData.Player2.Draw(3);

        context.Phase = Phase.Turn; //턴 시작 시 효과는 첫 턴 시작에 처리하지 않음.
    }
}