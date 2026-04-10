namespace SeaEngine.GameDataManager;

public partial class GameData
{
    public override string ToString()
    {
        return $@"
Turn: {Turn}
ActivePlayer: {ActivePlayerId}
Result: {Result}
Winner: {WinnerId ?? "-"}

{Board}
{Board.ToString2()}

Player1 Hand:
{Player1.Hand}

Player1 Trash:
{Player1.Trash}

Player1 Deck:
{Player1.Deck}

Player2 Hand:
{Player2.Hand}

Player2 Trash:
{Player2.Trash}

Player2 Deck:
{Player2.Deck}
";
    }
}
