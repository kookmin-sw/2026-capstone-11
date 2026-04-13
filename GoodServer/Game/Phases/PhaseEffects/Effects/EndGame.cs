using GoodServer.Game.Effects;

namespace GoodServer.Game.Phases.PhaseEffects.Effects;

[PhaseEffect(Phase.EndGame)]
public class EndGame : IEffect
{
    public string Description => "Game End";

    public async Task Execute(IGameContext context)
    {
        //굳이 뭘 할 건 없음
    }
}