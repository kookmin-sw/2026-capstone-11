using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public partial class GameData
{
    private static readonly List<(int, int)> _pawnAttackP1 = [(1, -1), (1, 1)];
    private static readonly List<(int, int)> _pawnAttackP2 = [(-1, -1), (-1, 1)];

    public List<(int, int)> GetAttackArea(Card card)
    {
        var attackArea = new List<(int, int)>();
        if (!card.Unit.IsPlaced) return attackArea;

        var x = card.Unit.PosX;
        var y = card.Unit.PosY;

        if (card.Data.UnitType == UnitType.Leader)
        {
            attackArea = attackArea.Concat(_kingStyle
                .Select(v => (v.Item1 + x, v.Item2 + y))
                .Where(v => v.Item1 is >= 0 and < 6 && v.Item2 is >= 0 and < 6))
                .ToList();
        }

        if (card.Data.UnitType == UnitType.Knight)
        {
            attackArea = attackArea.Concat(_knightStyle
                .Select(v => (v.Item1 + x, v.Item2 + y))
                .Where(v => v.Item1 is >= 0 and < 6 && v.Item2 is >= 0 and < 6))
                .ToList();
        }

        if (card.Data.UnitType == UnitType.Pawn)
        {
            var deltas = card.Owner == Player1 ? _pawnAttackP1 : _pawnAttackP2;
            attackArea = attackArea.Concat(deltas
                .Select(v => (v.Item1 + x, v.Item2 + y))
                .Where(v => v.Item1 is >= 0 and < 6 && v.Item2 is >= 0 and < 6))
                .ToList();
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
                    if (!(cx is >= 0 and < 6 && cy is >= 0 and < 6)) break;
                    attackArea.Add((cx, cy));
                    if (!Board.IsEmptyCell(cx, cy)) break;
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
                    if (!(cx is >= 0 and < 6 && cy is >= 0 and < 6)) break;
                    attackArea.Add((cx, cy));
                    if (!Board.IsEmptyCell(cx, cy)) break;
                }
            }
        }

        return attackArea;
    }
}
