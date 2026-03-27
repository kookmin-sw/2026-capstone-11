using SeaEngine.GameDataManager.Components;

namespace SeaEngine.GameDataManager;

public partial class GameData 
{
    public Player GetPlayer(string playerId)
    {
        if (Player1.Id == playerId) return Player1;
        if (Player2.Id == playerId) return Player2;
        throw new InvalidOperationException();
    }

    public void Reconstruct(string playerId)
    {
        Reconstruct(GetPlayer(playerId) ?? throw new InvalidOperationException());
    }
    public void Reconstruct(Player player)
    {
        foreach (var card in player.Trash.Cards)
            player.Deck.AddCard(card);
        player.Trash.Clear();
        player.Deck.Shuffle();
    }

    public void DrawCard(string playerId, int count)
    {
        DrawCard(GetPlayer(playerId) ?? throw new InvalidOperationException(), count);
    }
    
    public void DrawCard(Player player, int count)
    {
        for (int i = 0; i < count; i++)
        {
            if(player.Deck.Count == 0) Reconstruct(player);
            if(player.Deck.Count == 0) return;

            var top = player.Deck.Cards[0];
            player.Hand.AddCard(top);
            player.Deck.RemoveCard(top);
        }
    }

    public CardZone GetCardZoneById(Guid guid)
    {
        var target = Board.GetCardById(guid);
        var owner = target.Owner;
        if (owner.Deck.HasCard(target)) return owner.Deck;
        if (owner.Hand.HasCard(target)) return owner.Hand;
        if (owner.Trash.HasCard(target)) return owner.Trash;
        throw new InvalidOperationException();
    }

    public Card GetCardById(Guid guid)
    {
        return Board.GetCardById(guid);
    }

    public void TrashCard(Card card)
    {
        TrashCard(card.Guid);
    }
    public void TrashCard(Guid cardId)
    {
        var targetZone = GetCardZoneById(cardId);
        var targetCard = Board.GetCardById(cardId);
        targetZone.RemoveCard(targetCard);
        targetCard.Owner.Trash.AddCard(targetCard);
    }
}