using System.Text;
using SeaEngine.Common;

namespace SeaEngine.GameDataManager.Components;

public class Board
{
    public const int BoardSize = 6;
    
    public static readonly IReadOnlyList<(int, int)> Player1Zone = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)];
    public static readonly IReadOnlyList<(int, int)> Player2Zone = [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5)];
    
    private List<Card> _cards = [];
    public IReadOnlyList<Card> Cards => _cards;

    public void Register(Card card)
    {
        _cards.Add(card);
    }

    public bool IsEmptyCell(int x, int y)
    {
        return !_cards.Any(c => c.Unit.PosX == x && c.Unit.PosY == y);
    }

    public Card GetCardByPos(int x, int y)
    {
        int index = _cards.FindIndex(c => c.Unit.PosX == x && c.Unit.PosY == y);
        return index == -1 ? throw new InvalidOperationException("Cannot find card by pos(maybe cell is empty)") : _cards[index];
    }

    public Card GetCardById(Uid guid)
    {
        return _cards.Find(c => c.Guid == guid) ?? throw new InvalidOperationException();
    }

    public override string ToString()
    {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < BoardSize; i++)
        {
            for (int j = 0; j < BoardSize; j++)
            {
                sb.Append(IsEmptyCell(i, j) ? "-" : UnitTypeIcon.Get(GetCardByPos(i, j)!.Data.UnitType, GetCardByPos(i, j)!.Owner.Id == "Player1"));
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