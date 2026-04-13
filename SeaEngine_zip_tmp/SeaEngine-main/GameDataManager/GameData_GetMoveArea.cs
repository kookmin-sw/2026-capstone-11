using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public partial class GameData
{
    private static List<(int, int)> _kingStyle = [(1, -1), (1, 0), (1, 1), (0, -1), (0, 1), (-1, -1), (-1, 0), (-1, 1)];
    private static List<(int, int)> _knightStyle =
        [(2, -1), (2, 1), (1, -2), (1, 2), (-1, -2), (-1, 2), (-2, -1), (-2, 1)];

    private static List<(int, int)> _bishopStyle = [(-1, -1), (-1, 1), (1, 1), (1, -1)];
    private static List<(int, int)> _rookStyle = [(-1, 0), (1, 0), (0, -1), (0, 1)];
    
    public List<(int, int)> GetMoveArea(Card card)
    {
        
        var moveArea = new List<(int, int)>();
        if(!card.Unit.IsPlaced) return moveArea;

        var x = card.Unit.PosX;
        var y = card.Unit.PosY;
        
        if (card.Data.UnitType == UnitType.Leader)
        {
            moveArea = moveArea.Concat(_kingStyle
                .Select( v => (v.Item1 + x, v.Item2 + y))
                .Where(v =>  
                    v.Item1 is >= 0 and < Board.BoardSize && 
                    v.Item2 is >= 0 and < Board.BoardSize)
                ).ToList();
        }

        if (card.Data.UnitType == UnitType.Knight)
        {
            moveArea = moveArea.Concat(_knightStyle
                .Select( v => (v.Item1 + x, v.Item2 + y))
                .Where(v =>  
                    v.Item1 is >= 0 and < Board.BoardSize && 
                    v.Item2 is >= 0 and < Board.BoardSize)
            ).ToList();
        }

        if (card.Data.UnitType == UnitType.Pawn)
        {
            if(card.Owner == Player1 && x != 5) moveArea.Add((x + 1, y));
            if(card.Owner == Player2 && x != 0) moveArea.Add((x - 1, y));
        }

        if (card.Data.UnitType is UnitType.Bishop or UnitType.Queen)
        {
            foreach (var (dx, dy) in _bishopStyle)
            {
                var (cx, cy) = (x, y);
                while (true)
                {
                    cx += dx;
                    cy += dy;

                    if (!(cx is >= 0 and < Board.BoardSize && cy is >= 0 and < Board.BoardSize)) break;
                    moveArea.Add((cx, cy));
                    if(!Board.IsEmptyCell(cx, cy)) break;
                }
            }   
        }
        if (card.Data.UnitType is UnitType.Rook or UnitType.Queen)
        {
            foreach (var (dx, dy) in _rookStyle)
            {
                var (cx, cy) = (x, y);
                while (true)
                {
                    cx += dx;
                    cy += dy;

                    if (!(cx is >= 0 and < Board.BoardSize && cy is >= 0 and < Board.BoardSize)) break;
                    moveArea.Add((cx, cy));
                    if(!Board.IsEmptyCell(cx, cy)) break;
                }
            }   
        }
        return moveArea;
    }
}