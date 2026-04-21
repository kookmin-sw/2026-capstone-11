namespace SeaEngine.Common;

public enum UnitType
{
    Leader,
    Pawn,
    Knight,
    Bishop,
    Rook,
    Queen,
}

public static class UnitTypeIcon
{
    public static string Get(UnitType type, bool color)
    {
        switch (type)
        {
            case UnitType.Leader:
                return color ? "♔" : "♚";
            case UnitType.Pawn:
                return color ? "️♙" : "♟";
            case UnitType.Knight:
                return color ? "♘" : "♞";
            case UnitType.Bishop:
                return color ? "♗" : "♝";
            case UnitType.Rook:
                return color ? "♖" : "♜";
            case UnitType.Queen:
                return color ? "♕" : "♛";
            default:
                throw new ArgumentOutOfRangeException(nameof(type), type, null);
        }
    }
}