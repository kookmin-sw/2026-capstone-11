using System.Text;
using SeaEngine.Common;

namespace SeaEngine.GameDataManager.Components;

public class Board
{
    public const int BoardSize = 6;
    
    public static readonly IReadOnlyList<(int, int)> Player1Zone = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)];
    public static readonly IReadOnlyList<(int, int)> Player2Zone = [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5)];
    
    private readonly List<Card> _cards = [];
    private readonly Dictionary<Uid, Card> _cardById = new();
    private readonly Card?[,] _grid = new Card[BoardSize, BoardSize];
    public IReadOnlyList<Card> Cards => _cards;

    public void Register(Card card)
    {
        _cards.Add(card);
        _cardById[card.Guid] = card;
    }

    public void ReconstructFrom(IReadOnlyList<Card> cards)
    {
        for (int i = 0; i < cards.Count; i++)
        {
            var card = cards[i];
            _cards.Add(card);
            _cardById[card.Guid] = card;
            if (card.Unit.IsPlaced)
            {
                var x = card.Unit.PosX;
                var y = card.Unit.PosY;
                if (x is >= 0 and < BoardSize && y is >= 0 and < BoardSize)
                    _grid[x, y] = card;
            }
        }
    }

    public bool IsEmptyCell(int x, int y) => _grid[x, y] == null;

    public Card GetCardByPos(int x, int y) =>
        _grid[x, y] ?? throw new InvalidOperationException("Cannot find card by pos(maybe cell is empty)");

    public Card GetCardById(Uid guid) =>
        _cardById.TryGetValue(guid, out var card) ? card : throw new InvalidOperationException();

    public void PlaceCard(Card card, int x, int y)
    {
        if (x is < 0 or >= BoardSize || y is < 0 or >= BoardSize)
            throw new ArgumentOutOfRangeException($"Place Out of range({card.Guid})");
        if (_grid[x, y] != null)
            throw new InvalidOperationException($"Cell ({x}, {y}) is already occupied");
        card.Unit.Place(x, y);
        _grid[x, y] = card;
    }

    public void MoveCard(Card card, int x, int y)
    {
        if (x is < 0 or >= BoardSize || y is < 0 or >= BoardSize)
            throw new ArgumentOutOfRangeException($"Move Out of range({card.Guid})");
        _grid[card.Unit.PosX, card.Unit.PosY] = null;
        card.Unit.Move(x, y);
        _grid[x, y] = card;
    }

    public void SwapCards(Card card1, Card card2)
    {
        int x1 = card1.Unit.PosX;
        int y1 = card1.Unit.PosY;
        
        _grid[card1.Unit.PosX, card1.Unit.PosY] = null;
        _grid[card2.Unit.PosX, card2.Unit.PosY] = null;
        card1.Unit.Move(card2.Unit.PosX, card2.Unit.PosY);
        card2.Unit.Move(x1, y1);
        _grid[card1.Unit.PosX, card1.Unit.PosY] = card1;
        _grid[card2.Unit.PosX, card2.Unit.PosY] = card2;
    }

    public void WithdrawCard(Card card)
    {
        if (!card.Unit.IsPlaced) return;
        _grid[card.Unit.PosX, card.Unit.PosY] = null;
        card.Unit.Withdraw();
    }

    public override string ToString()
    {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < BoardSize; i++)
        {
            for (int j = 0; j < BoardSize; j++)
            {
                var cell = _grid[i, j];
                sb.Append(cell == null ? "-" : UnitTypeIcon.Get(cell.Data.UnitType, cell.Owner.Id == "Player1"));
            }
            sb.Append('\n');
        }
        return sb.ToString();
    }

    public string ToString2()
    {
        StringBuilder sb = new StringBuilder();
        foreach (var card in _cards)
        {
            sb.Append($"{card.Guid}, {card.Owner.Id}, {card.Data.Id}, {card.Unit.PosX} / {card.Unit.PosY}\n");
        }
        return sb.ToString();
    }
}