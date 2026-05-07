using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public partial class GameData
{
    public GameData Clone()
    {
        var totalCards = Player1.Hand.Count + Player1.Deck.Count + Player1.Trash.Count
                       + Player2.Hand.Count + Player2.Deck.Count + Player2.Trash.Count;

        var ctx = new GameCloneContext(playerCapacity: 2, cardCapacity: totalCards);

        var clonedPlayer1 = Player1.Clone(ctx);
        var clonedPlayer2 = Player2.Clone(ctx);

        var board = new Board();
        board.ReconstructFrom(Board.Cards.Select(c => ctx.GetCloned(c)).ToList());

        var clonedActivePlayer = ActivePlayer == Player1 ? clonedPlayer1 : clonedPlayer2;
        var clonedWinner = Winner != null ? (Winner == Player1 ? clonedPlayer1 : clonedPlayer2) : null;

        return new GameData(clonedPlayer1, clonedPlayer2, board, Logger, clonedActivePlayer, clonedWinner, TurnCnt);
    }
}
