using GoodServer.Game.Effects;
using GoodServer.Game.GameData;

namespace GoodServer.Game.Phases.PhaseEffects.Effects;

[PhaseEffect(Phase.Turn)]
public class Turn: IEffect
{
    public string Description => "On Turn";
    public async Task Execute(IGameContext context)
    {
        var turnMove = await context.InteractionContext.GetTurnMove(context, context.TurnPlayer);
        switch (turnMove.MoveType)
        {
            case TurnMove.Type.UseCard:
                var card = turnMove.GetCard();
                if(card == null) throw new Exception("No card found in TurnMove(Maybe Wrong Type...)");
                //TODO: 카드 효과 사용
                context.TurnPlayer.UseCard(card);
                break;
            case TurnMove.Type.BasicMove:
                var unit = turnMove.GetUnit();
                if (unit == null) throw new Exception("No unit found in TurnMove(Maybe Wrong Type...)");
                //TODO: 유닛 이동
                break;
            case TurnMove.Type.TurnEnd:
                context.Phase = Phase.TurnEnd;
                break;
            default:
                throw new ArgumentOutOfRangeException();
        }
    }
}