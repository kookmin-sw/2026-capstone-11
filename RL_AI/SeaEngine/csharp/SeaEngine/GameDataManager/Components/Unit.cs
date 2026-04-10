namespace SeaEngine.GameDataManager.Components;

public class Unit(Card card)
{
    public readonly Card Card = card;
    private readonly List<UnitStatus> _statuses = [];

    public int Atk = card.Data.Atk;
    public int MaxHp = card.Data.Hp;
    public int Hp = card.Data.Hp;

    public bool IsPlaced = false; // 설치된 유닛인지
    public bool IsMoved = false; // 이번 턴에 기본행동으로 움직였는지
    public bool IsAttacked = false; // 이번 턴에 공격했는지
    public IReadOnlyList<UnitStatus> Statuses => _statuses;

    public int PosX = -1;
    public int PosY = -1;

    public int EffectiveAtk => Math.Max(0, Atk + _statuses
        .Where(status => status.Type == UnitStatusType.AttackModifier)
        .Sum(status => status.Value));
    public bool HasMoveLock => _statuses.Any(status => status.Type == UnitStatusType.MoveLock);
    public bool HasAttackLock => _statuses.Any(status => status.Type == UnitStatusType.AttackLock);
    public bool CanBasicMove => IsPlaced && !IsMoved && !HasMoveLock;
    public bool CanBasicAttack => IsPlaced && !IsAttacked && !HasAttackLock;

    public void Place(int x, int y)
    {
        IsPlaced = true;
        IsMoved = false;
        IsAttacked = false;
        _statuses.Clear();
        PosX = x;
        PosY = y;
    }

    public void Move(int x, int y)
    {
        //주의 : 가능 여부 체크 안 함.
        PosX = x;
        PosY = y;
    }

    public void Withdraw()
    {
        IsPlaced = false;
        IsMoved = false;
        IsAttacked = false;
        _statuses.Clear();
        PosX = -1;
        PosY = -1;
    }

    public void AddOrRefreshStatus(UnitStatusType type, int value, int remainingTurns, string sourceKey)
    {
        var existing = _statuses.FirstOrDefault(status => status.Type == type && status.SourceKey == sourceKey);
        if (existing != null)
        {
            existing.Refresh(value, remainingTurns);
            return;
        }

        _statuses.Add(new UnitStatus(type, value, remainingTurns, sourceKey));
    }

    public void RemoveStatus(UnitStatusType type, string sourceKey)
    {
        _statuses.RemoveAll(status => status.Type == type && status.SourceKey == sourceKey);
    }

    public void TickStatuses()
    {
        for (var i = _statuses.Count - 1; i >= 0; i--)
        {
            if (_statuses[i].Tick())
            {
                _statuses.RemoveAt(i);
            }
        }
    }

    public void ResetForNewTurn()
    {
        IsMoved = false;
        IsAttacked = false;
    }
}
