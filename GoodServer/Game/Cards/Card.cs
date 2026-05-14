using GoodServer.Game.GameData.Board.Units;

namespace GoodServer.Game.Cards;

public class Card(string id)
{
    public string Id => id; //ex. 03B1 -> 03번째 덱의 Bishop
    public bool Enabled { get; set; } = true;
    
    //Data에 접근하는 방법 만들기
}