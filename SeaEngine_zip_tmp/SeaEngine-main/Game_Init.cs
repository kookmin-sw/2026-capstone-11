using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;
using Newtonsoft.Json;

namespace SeaEngine;

public partial class Game
{
    public void Init(string player1Deck, string player2Deck)
    {
        var player1DeckList = ParseDeck(player1Deck);
        var player2DeckList = ParseDeck(player2Deck);
        
        Data.Init(player1DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player1)).ToList(),  
            player2DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player2)).ToList());
        
        Data.Player1.Deck.Shuffle();
        Data.Player2.Deck.Shuffle();

        if (Data.Player1.Deck.Cards.All(c => c.Data.UnitType != UnitType.Leader))
            throw new InvalidOperationException("No Leader in Player 1 Deck");
        if (Data.Player2.Deck.Cards.All(c => c.Data.UnitType != UnitType.Leader))
            throw new InvalidOperationException("No Leader in Player 2 Deck");
        
        Data.Player1.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(0, 2);
        Data.Player2.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(5, 3);
        
        Data.DrawCard(Data.Player1, 3);  
        Data.DrawCard(Data.Player2, 3);  
        
        Data.TriggerEventToAll("TurnStart");
        Data.TriggerBuffEventToAll("TurnStart");
        
        UpdateActions();
    }

    private static List<string> ParseDeck(string deckJson)
    {
        if (string.IsNullOrWhiteSpace(deckJson))
        {
            throw new ArgumentException("Deck JSON cannot be empty.");
        }

        var deck = JsonConvert.DeserializeObject<List<string>>(deckJson);
        if (deck == null || deck.Count == 0)
        {
            throw new ArgumentException("Deck JSON must be a non-empty JSON array of card IDs.");
        }

        if (deck.Any(string.IsNullOrWhiteSpace))
        {
            throw new ArgumentException("Deck JSON cannot contain empty card IDs.");
        }

        return deck;
    }
}
