using GoodServer.Game.Cards;

namespace GoodServer.Game.GameData;

public class Player(string id)
{
    private static readonly Random Random = new Random();
    
    public string Id {get; private set;} = id;

    private readonly List<Card> _hand = [];
    private readonly List<Card> _deck = [];
    private readonly List<Card> _used = [];
    
    public IReadOnlyList<Card> Hand => _hand;
    public IReadOnlyList<Card> Deck => _deck;
    public IReadOnlyList<Card> Used => _used;

    public void SetDeck(List<Card> deck)
    {
        _deck.Clear();
        _deck.AddRange(deck);
        Shuffle();
    }

    public void Shuffle()
    {
        for(int i = 0; i < _deck.Count - 1; i++)
        {
            int n = Random.Next(i, _deck.Count);
            (_deck[i], _deck[n]) = (_deck[n], _deck[i]);
        }
    }
    
    public bool Reconstruct()
    {
        if(_used.Count == 0) return false;
        
        _deck.AddRange(_used);
        _used.Clear();
        Shuffle();
        return true;
    }
    
    public bool Draw()
    {
        if(_deck.Count == 0) return false;
        
        _hand.Add(_deck[0]);
        _deck.RemoveAt(0);
        return true;
    }

    public int Draw(int count)
    {
        int drawCount = 0;
        for (drawCount = 0; drawCount < count; drawCount++)
            if (!Draw()) break;

        return drawCount;
    }

    public bool UseCard(Card card)
    {
        if (!_hand.Contains(card)) return false;
        
        _used.Add(card);
        _hand.Remove(card);
        return true;
    }

    public void Discard(Card card)
    {
        _hand.Remove(card);
    }
}