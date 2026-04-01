using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public partial class GameData
{
    public readonly Player Player1;
    public readonly Player Player2;
    public Player ActivePlayer;
    public readonly Board Board = new Board();

    public GameData(string player1Id, string player2Id)
    {
        Player1 = new Player(player1Id);
        Player2 = new Player(player2Id);
        ActivePlayer = Player1;
    }

    public void Init(List<Card> player1Cards, List<Card> player2Cards)
    {
        foreach (var card in player1Cards)
        {
            Board.Register(card);
            Player1.Deck.AddCard(card);
        }

        foreach (var card in player2Cards)
        {
            Board.Register(card);
            Player2.Deck.AddCard(card);
        }
    }
}