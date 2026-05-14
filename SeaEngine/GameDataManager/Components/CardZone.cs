using System.Text;
using SeaEngine.Common;

namespace SeaEngine.GameDataManager.Components;

public class CardZone
{
    private List<Card> _cards = [];
    public IReadOnlyList<Card> Cards => _cards;
    public int Count => _cards.Count;

    public void AddCard(Card card)
    {
        _cards.Add(card);
    }

    public void RemoveCard(Card card)
    {
        _cards.Remove(card);
    }

    public void RemoveCard(Uid guid)
    {
        _cards.RemoveAll(card => card.Guid == guid);
    }

    public bool HasCard(Card card)
    {
        return HasCard(card.Guid);
    }

    public bool HasCard(Uid guid)
    {
        return _cards.Any(card => card.Guid == guid);
    }

    public void Clear()
    {
        _cards.Clear();
    }

    public void Shuffle()
    {
        for (int i = _cards.Count - 1; i > 0; i--)
        {
            int j = Random.Shared.Next(i + 1);
            (_cards[i], _cards[j]) = (_cards[j], _cards[i]);
        }
    }
    
    public CardZone(){}
    public CardZone(List<Card> cards)
    {
        _cards = cards;
    }

    public CardZone Clone(GameCloneContext ctx)
    {
        var clonedCards = new List<Card>(_cards.Count);
        foreach (var card in _cards)
            clonedCards.Add(ctx.GetOrClone(card));
        return new CardZone(clonedCards);
    }

    public override string ToString()
    {
        StringBuilder sb = new StringBuilder();
        foreach (var card in _cards)
        {
            sb.Append($"{card}\n");
        }
        return sb.ToString();
    }
}