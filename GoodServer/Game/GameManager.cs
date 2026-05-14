using GoodServer.Game.Effects;
using GoodServer.Game.GameData;
using GoodServer.Game.Phases;
using GoodServer.Game.Phases.PhaseEffects;
using GoodServer.Interaction;

namespace GoodServer.Game;

public class GameManager(Player player1, Player player2) : IGameContext
{
    public GameData.GameData GameData { get; } = new GameData.GameData(player1, player2);

    public IInteractionContext InteractionContext => throw new NotImplementedException();

    public Player TurnPlayer { get; private set; } = player1;

    public Phase Phase { get; set; } = Phase.PreGame;
    
    //Game이 정상적으로 종료되었는지 여부
    public async Task<bool> RunGame()
    {
        while (true)
        { 
            Console.WriteLine(GameData.Player1.Id + " : " + Phase);
            
            //현재 페이즈에 할 일을 찾아서 적용합니다.
            IEffect? curPhaseEffect = PhaseEffectRegistry.Get(Phase);
            if (curPhaseEffect == null) throw new Exception("No effect on Phase : " + Phase);
            await curPhaseEffect.Execute(this);
            
            //TODO: 뭔가 했으면 상태참조를 합니다.
            
            //EndGame페이즈가 끝나면 게임 실행을 종료합니다.
            if (Phase == Phase.EndGame)
            {
                //여기서 승자 처리를 해야 하나 고민. -> 승자 처리는 상태참조에서 합시다.
                //그럼 Endgame 페이즈가 필요한가요?
                return true;
            }
        }
    }

    public void SwitchTurnPlayer()
    {
        TurnPlayer = (TurnPlayer == GameData.Player1) ? GameData.Player2 : GameData.Player1;
    }
}