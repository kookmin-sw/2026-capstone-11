using GoodServer.Game.GameData.Board.Units;
using GoodServer.Library;

namespace GoodServer.Game.GameData.Board;

public class BoardManager
{
    public const int BoardSize = 6;
    private readonly Unit?[,] _board = new Unit?[BoardSize, BoardSize];

    public IUnit? this[int x, int y] => _board[x, y];
    public IUnit? this[Vector2Int pos] => _board[pos.X, pos.Y];

    public void PlaceUnit(Unit unit)
    {
        _board[unit.Position.X, unit.Position.Y] = unit;
    }
    
    public void MoveUnit(IUnit unit, int x, int y)
    {
        var curUnit = _board[unit.Position.X, unit.Position.Y];
        _board[unit.Position.X, unit.Position.Y] = null;
        
        curUnit?.Position = (x, y);
        _board[x, y] = curUnit;
    }

    public void SwapUnit(IUnit unit1, IUnit unit2)
    {
        var curUnit1 = _board[unit1.Position.X, unit1.Position.Y];
        var curUnit2 = _board[unit2.Position.X, unit2.Position.Y];
        
        _board[unit1.Position.X, unit1.Position.Y] = null;
        _board[unit2.Position.X, unit2.Position.Y] = null;

        _board[unit1.Position.X, unit1.Position.Y] = curUnit2;
        _board[unit2.Position.X, unit2.Position.Y] = curUnit1;
        curUnit1?.Position = (unit2.Position.X, unit2.Position.Y);
        curUnit2?.Position = (unit1.Position.X, unit1.Position.Y);
    }

    public void RemoveUnit(IUnit unit)
    {
        _board[unit.Position.X, unit.Position.Y] = null;
    }

    public List<IUnit> GetUnits()
    {
        var units = new List<IUnit>();
        for (int i = 0; i <= BoardSize; i++)
        {
            for (int j = 0; j <= BoardSize; j++)
            {
                if(_board[i, j] != null) units.Add(_board[i, j]!);
            }
        }
        return units;
    }

    public void HitUnit(IUnit unit, int damage)
    {
        var curUnit = _board[unit.Position.X, unit.Position.Y];
        curUnit?.CurrentHp -= damage;
    }
}