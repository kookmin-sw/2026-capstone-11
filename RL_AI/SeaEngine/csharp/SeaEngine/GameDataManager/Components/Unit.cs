namespace SeaEngine.GameDataManager.Components;

public class Unit
{
    public readonly Card Card;

    public int Atk;
    public int MaxHp;
    public int Hp;

    public bool IsPlaced = false; // 설치된 유닛인지
    public bool IsMoved = false; // 이번 턴에 기본행동으로 움직였는지
    
    public int PosX = -1;
    public int PosY = -1;

    public Unit(Card card)
    {
        Card = card;
        Atk = card.Data.Atk;
        MaxHp = card.Data.Hp;
        Hp = card.Data.Hp;
    }

    public void Place(int x, int y)
    {
        if (x is < 0 or >= Board.BoardSize || y is < 0 or >= Board.BoardSize)
        {
            throw new ArgumentOutOfRangeException($"Place Out of range({Card.Guid})");
        }
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

    public Dictionary<string, int> Buffs = new Dictionary<string, int>();
    
    public void GiveBuff(string buff, int amount = 1)
    {
        Buffs.TryAdd(buff, 0);
        Buffs[buff] += amount;
    }

    public void RemoveBuff(string buff)
    {
        Buffs.Remove(buff);
    }
}
