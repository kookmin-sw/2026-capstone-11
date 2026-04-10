using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;
using System.Text.Json;

namespace SeaEngine;

public partial class Game
{
    public void Init(string player1Deck, string player2Deck)
    {
        List<string> player1DeckList = ParseDeck(player1Deck, ["Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P"]);
        List<string> player2DeckList = ParseDeck(player2Deck, ["Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P"]);
        
        Data.Init(player1DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player1)).ToList(),  
            player2DeckList.Select(id => new Card(CardLoader.GetCard(id), Data.Player2)).ToList());
        
        Data.Player1.Deck.Shuffle();
        Data.Player2.Deck.Shuffle();
        
        Data.Player1.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(0, 2);
        Data.Player2.Deck.Cards.First(c => c.Data.UnitType == UnitType.Leader).Unit.Place(5, 3);
        
        Data.DrawCard(Data.Player1, 3);  
        Data.DrawCard(Data.Player2, 3);  
        AutoMulligan(Data.Player1);
        AutoMulligan(Data.Player2);
        
        Data.ActivePlayer = Random.Shared.Next(2) == 0 ? Data.Player1 : Data.Player2;
        Data.ResetMovementForTurn(Data.ActivePlayer);
        Data.DrawCard(Data.ActivePlayer, 2);
        Data.ApplyTimedEvents("TurnStart");
        Data.UpdateResult();
        UpdateActions();
    }

    private static List<string> ParseDeck(string deckText, IEnumerable<string> fallback)
    {
        if (string.IsNullOrWhiteSpace(deckText))
        {
            return fallback.ToList();
        }

        try
        {
            var parsed = JsonSerializer.Deserialize<List<string>>(deckText);
            if (parsed is { Count: > 0 }) return parsed;
        }
        catch
        {
            // fall through to simple splitting
        }

        var split = deckText
            .Split([',', '\n', '\r', ' ', '\t'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .ToList();
        return split.Count > 0 ? split : fallback.ToList();
    }

    private static void AutoMulligan(Player player)
    {
        var hand = player.Hand.Cards.ToList();
        var hasPawn = hand.Any(card => card.Data.UnitType == UnitType.Pawn);
        var hasOtherUnit = hand.Any(card => card.Data.UnitType != UnitType.Leader && card.Data.UnitType != UnitType.Pawn);
        if (hasPawn || hasOtherUnit) return;

        foreach (var card in hand)
        {
            player.Hand.RemoveCard(card);
            player.Deck.AddCard(card);
        }
        player.Deck.Shuffle();
        for (var i = 0; i < 3 && player.Deck.Count > 0; i++)
        {
            var top = player.Deck.Cards[0];
            player.Hand.AddCard(top);
            player.Deck.RemoveCard(top);
        }
    }
}
