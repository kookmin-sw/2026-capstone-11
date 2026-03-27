namespace SeaEngine.GameDataManager.Components;

public class Unit(Card card)
{
    public readonly Card Card = card;

    public int Atk = card.Data.Atk;
    public int MaxHp = card.Data.Hp;
    public int Hp = card.Data.Hp;

    public bool IsPlaced = false; // 설치된 유닛인지
    public bool IsMoved = false; // 이번 턴에 기본행동으로 움직였는지
    
    public int PosX = -1;
    public int PosY = -1;

    public void Place(int x, int y)
    {
        IsPlaced = true;
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
        PosX = -1;
        PosY = -1;
    }
    //TODO: 버프/디버프 만들기.
}