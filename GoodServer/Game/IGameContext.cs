using GoodServer.Game.GameData;
using GoodServer.Game.Phases;
using GoodServer.Interaction;

namespace GoodServer.Game;

public interface IGameContext
{
    GameData.GameData GameData { get; }
    IInteractionContext InteractionContext { get; }
    Phase Phase { get; set; }
    Player TurnPlayer { get; }
    void SwitchTurnPlayer();
}