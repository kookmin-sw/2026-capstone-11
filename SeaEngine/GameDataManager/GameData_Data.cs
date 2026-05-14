using Newtonsoft.Json;
using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;
using SeaEngine.GameDataManager.Converters;
using SeaEngine.GameEventManager;
using SeaEngine.Logger;

namespace SeaEngine.GameDataManager;

public partial class GameData
{
    public readonly Player Player1;
    public readonly Player Player2;
    [JsonIgnore]
    public Player? Winner;
    public string WinnerId => Winner?.Id ?? "";
    
    [JsonIgnore] public Player ActivePlayer;
    [JsonIgnore] public readonly ILogger Logger;
    public string ActivePlayerId => ActivePlayer.Id;
    public readonly Board Board = new Board();
    public int TurnCnt = 0;

    public GameData(string player1Id, string player2Id, ILogger logger)
    {
        Logger = logger;
        Player1 = new Player(player1Id);
        Player2 = new Player(player2Id);
        ActivePlayer = Player1;
        Winner = null;
    }

    private GameData(Player player1, Player player2, Board board, ILogger logger, Player activePlayer, Player? winner, int turnCnt)
    {
        Player1 = player1;
        Player2 = player2;
        Board = board;
        Logger = logger;
        ActivePlayer = activePlayer;
        Winner = winner;
        TurnCnt = turnCnt;
    }

    public void Init(List<Card> player1Cards, List<Card> player2Cards)
    {
        foreach (var card in player1Cards)
        {
            Board.Register(card);
            Player1.Deck.AddCard(card);
        }

        foreach (var card in player2Cards)
        {
            Board.Register(card);
            Player2.Deck.AddCard(card);
        }
    }

    private static readonly JsonConverter[] SerializeConverters =
        [new CardZoneConverter(), new CardConverter(), new BoardConverter()];

    public string Serialize()
    {
        return JsonConvert.SerializeObject(this, Formatting.Indented, SerializeConverters);
    }

    public void TriggerEvent(string eventId, string timing, Uid source)
    {
        if (EventRegistry.GetEvent(timing, eventId)?.Apply(source, this) ?? false)
        {
            Logger.LogEvent(eventId, timing, source);
        }
    }

    public void TriggerEventToAll(string timing)
    {
        foreach (var boardCard in Board.Cards)
        {
            if (!boardCard.Unit.IsPlaced) continue;
            TriggerEvent(boardCard.Data.EventId, timing, boardCard.Guid);
        }
        TriggerEvent("Rule", timing, Uid.None);
    }

    public void TriggerBuffEventToAll(string timing)
    {
        foreach (var boardCard in Board.Cards)
        {
            if(!boardCard.Unit.IsPlaced) continue;
            foreach (var buff in boardCard.Unit.Buffs)
            {
                TriggerEvent(buff.Key, timing, boardCard.Guid);
            }
        }
    }
    
    public void TriggerBeforeAttackEvent(string eventId, Uid source, Uid target)
    {
        if (EventRegistry.GetAttackEvent(eventId)?.BeforeAttack(source, target,this) ?? false)
        {
            Logger.LogEvent(eventId, "BeforeAttack", source);
        }
    }
    public void TriggerAfterAttackEvent(string eventId, Uid source, Uid target)
    {
        if (EventRegistry.GetAttackEvent(eventId)?.AfterAttack(source, target,this) ?? false)
        {
            Logger.LogEvent(eventId, "AfterAttack", source);
        }
    }
    public void TriggerBeforeAttackedEvent(string eventId, Uid source, Uid target)
    {
        if (EventRegistry.GetAttackEvent(eventId)?.BeforeAttacked(source, target,this) ?? false)
        {
            Logger.LogEvent(eventId, "BeforeAttacked", source);
        }
    }
    public void TriggerAfterAttackedEvent(string eventId, Uid source, Uid target)
    {
        if (EventRegistry.GetAttackEvent(eventId)?.AfterAttacked(source, target,this) ?? false)
        {
            Logger.LogEvent(eventId, "AfterAttacked", source);
        }
    }
}