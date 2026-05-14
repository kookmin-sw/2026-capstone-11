using GoodServer.Library;

namespace GoodServer.Game.GameData.Board.Units;

public class Unit(string id, Player owner) : IUnit
{
    public string Id => id; //ex. 03B1 -> 03번째 덱의 Bishop
    public Player Owner => owner;
    public Vector2Int Position {  get; set; } = new Vector2Int(0, 0);
    public int CurrentHp { get; set; } = 0;
    
    //TODO : Data에 접근하는 방법 만들기
    //TODO : Buff 만들기
}