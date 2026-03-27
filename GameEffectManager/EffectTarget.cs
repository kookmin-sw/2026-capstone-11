using SeaEngine.Actions;

namespace SeaEngine.GameEffectManager;


public class EffectTarget
{
    public readonly Guid Guid;
    public readonly Guid Guid2;
    public readonly int PosX;
    public readonly int PosY;
    public readonly Types Type;

    private EffectTarget(Guid guid, Guid guid2,Types type, int posX, int posY)
    {
        Guid = guid;
        Guid2 = guid2;
        Type = type;
        PosX = posX;
        PosY = posY;
    }

    public enum Types
    {
        Unit,
        Unit2,
        Card,
        Cell,
        None,
    }
    
    public static readonly EffectTarget None = new EffectTarget(Guid.Empty, System.Guid.Empty, EffectTarget.Types.None, -1, -1);

    public static EffectTarget Unit(Guid guid)
    {
        return new EffectTarget(guid, System.Guid.Empty,EffectTarget.Types.Unit, -1, -1);
    }

    public static EffectTarget Unit2(Guid guid, Guid guid2)
    {
        return new EffectTarget(guid, guid2,EffectTarget.Types.Unit2, -1, -1);
    }

    public static EffectTarget Card(Guid guid)
    {
        return new EffectTarget(guid, System.Guid.Empty,EffectTarget.Types.Card, -1, -1);
    }

    public static EffectTarget Cell(int posX, int posY)
    {
        return new EffectTarget(Guid.Empty, System.Guid.Empty, EffectTarget.Types.Cell, posX, posY);
    }

    public override string ToString()
    {
        return Type switch
        {
            Types.Unit => $"{Guid}(unit)",
            Types.Unit2 => $"{Guid}(unit),{Guid2}(unit2)",
            Types.Card => $"{Guid}(card)",
            Types.Cell => $"{PosX}/{PosY}(cell)",
            Types.None => $"none",
            _ => throw new ArgumentOutOfRangeException()
        };
    }
}