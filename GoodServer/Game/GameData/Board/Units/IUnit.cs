using GoodServer.Library;

namespace GoodServer.Game.GameData.Board.Units;

public interface IUnit
{
    public string Id { get; }
    public Vector2Int Position { get; }
    public int CurrentHp { get; }
}