namespace SeaEngine.GameDataManager.Components;

public class Unit
{
    public Card Card = null!;
    public int Atk;
    public int MaxHp;
    public int Hp;
    public bool IsPlaced;
    public bool IsMoved;
    public int PosX = -1;
    public int PosY = -1;
    public readonly Dictionary<string, int> Buffs = new Dictionary<string, int>();

    public Unit(Card card)
    {
        Card = card;
        Atk = card.Data.Atk;
        MaxHp = card.Data.Hp;
        Hp = card.Data.Hp;
    }

    private Unit() { }

    public void Place(int x, int y)
    {
        if (x is < 0 or >= Board.BoardSize || y is < 0 or >= Board.BoardSize)
        {
            throw new ArgumentOutOfRangeException($"Place Out of range({Card.Guid})");
        }

        Atk = Card.Data.Atk;
        MaxHp = Card.Data.Hp;
        Hp = Card.Data.Hp;
        Buffs.Clear();

        IsPlaced = true;
        PosX = x;
        PosY = y;
    }

    public void Move(int x, int y)
    {
        if (x is < 0 or >= Board.BoardSize || y is < 0 or >= Board.BoardSize)
        {
            throw new ArgumentOutOfRangeException($"Move Out of range({Card.Guid})");
        }
        PosX = x;
        PosY = y;
    }

    public void Withdraw()
    {
        IsPlaced = false;
        PosX = -1;
        PosY = -1;
        Buffs.Clear();
    }

    public void GiveBuff(string buff, int amount = 1)
    {
        Buffs.TryAdd(buff, 0);
        Buffs[buff] += amount;
    }

    public void RemoveBuff(string buff)
    {
        Buffs.Remove(buff);
    }

    public Unit Clone()
    {
        var unit = new Unit();
        unit.Atk = Atk;
        unit.MaxHp = MaxHp;
        unit.Hp = Hp;
        unit.IsPlaced = IsPlaced;
        unit.IsMoved = IsMoved;
        unit.PosX = PosX;
        unit.PosY = PosY;
        if (Buffs.Count > 0)
            ((Dictionary<string, int>)unit.Buffs).EnsureCapacity(Buffs.Count);
        foreach (var (key, value) in Buffs)
            unit.Buffs[key] = value;
        return unit;
    }
}