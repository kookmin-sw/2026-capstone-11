using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;
using SeaEngine.GameEventManager;

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

    public CardZone GetCardZoneById(Uid guid)
    {
        var target = Board.GetCardById(guid);
        var owner = target.Owner;
        if (owner.Deck.HasCard(target)) return owner.Deck;
        if (owner.Hand.HasCard(target)) return owner.Hand;
        if (owner.Trash.HasCard(target)) return owner.Trash;
        throw new InvalidOperationException();
    }

    public Card GetCardById(Uid uid)
    {
        return Board.GetCardById(uid);
    }

    public void TrashCard(Card card)
    {
        TrashCard(card.Guid);
    }
    public void TrashCard(Uid cardId)
    {
        var targetZone = GetCardZoneById(cardId);
        var targetCard = Board.GetCardById(cardId);
        targetZone.RemoveCard(targetCard);
        targetCard.Owner.Trash.AddCard(targetCard);
    }

    public Card? GetLeader(Player player)
    {
        return Board.Cards.FirstOrDefault(c => c.Owner == player && c.Data.UnitType == UnitType.Leader);
    }

    public void UpdateResult()
    {
        var p1LeaderDead = !(GetLeader(Player1)?.Unit.IsPlaced ?? false);
        var p2LeaderDead = !(GetLeader(Player2)?.Unit.IsPlaced ?? false);

        if (p1LeaderDead && p2LeaderDead)
        {
            Result = GameResult.Draw;
            WinnerId = null;
        }
        else if (p1LeaderDead)
        {
            Result = GameResult.Player2Win;
            WinnerId = Player2.Id;
        }
        else if (p2LeaderDead)
        {
            Result = GameResult.Player1Win;
            WinnerId = Player1.Id;
        }
        else
        {
            Result = GameResult.Ongoing;
            WinnerId = null;
        }
    }

    public void ResetMovementForTurn(Player player)
    {
        foreach (var card in Board.Cards.Where(c => c.Owner == player && c.Unit.IsPlaced))
        {
            card.Unit.ResetForNewTurn();
        }
    }

    public void TickStatuses()
    {
        foreach (var card in Board.Cards.Where(c => c.Unit.IsPlaced))
        {
            card.Unit.TickStatuses();
        }
    }

    public void DiscardDownTo(Player player, int handLimit)
    {
        while (player.Hand.Count > handLimit)
        {
            var card = player.Hand.Cards.Last();
            player.Hand.RemoveCard(card);
            player.Trash.AddCard(card);
        }
    }

    public void ApplyTimedEvents(string timing)
    {
        foreach (var card in Board.Cards.Where(c => c.Unit.IsPlaced))
        {
            var evt = EventRegistry.GetEvent(timing, card.Data.EventId);
            evt?.Apply(card.Guid, this);
        }
    }

    public void ApplyDestroyedEvent(Card destroyedCard)
    {
        var evt = EventRegistry.GetEvent("OnDestroyed", destroyedCard.Data.EventId);
        evt?.Apply(destroyedCard.Guid, this);
    }

    public void ApplyBasicMoveEvent(Card movedCard)
    {
        var evt = EventRegistry.GetEvent("OnBasicMove", movedCard.Data.EventId);
        evt?.Apply(movedCard.Guid, this);
    }
}
