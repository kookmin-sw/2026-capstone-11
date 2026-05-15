using GoodServer.Game.GameData.Board;

namespace GoodServer.Game.GameData;

public class GameData(Player player1, Player player2)
{
    public readonly Player Player1 = player1;
    public readonly Player Player2 = player2;
    public readonly BoardManager Board = new BoardManager();
}