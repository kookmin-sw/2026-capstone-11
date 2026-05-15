namespace GoodServer.Library;

public record Vector2Int(int X = 0, int Y = 0)
{
    public int X = X;
    public int Y = Y;
    public static implicit operator Vector2Int((int x, int y) value) 
        => new(value.x, value.y);

    public override string ToString()
    {
        return $"({X},{Y})";
    }
}