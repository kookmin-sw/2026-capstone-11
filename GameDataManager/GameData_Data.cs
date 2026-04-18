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
    [JsonIgnore] public int TurnCnt = 0;

    public GameData(string player1Id, string player2Id, ILogger logger)
    {
        Logger = logger;
        Player1 = new Player(player1Id);
        Player2 = new Player(player2Id);
        ActivePlayer = Player1;
        Winner = null;
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

    public string Serialize()
    {
        return JsonConvert.SerializeObject(this, Formatting.Indented, [new CardZoneConverter(), new CardConverter(), new BoardConverter()]);
    }

    public void TriggerEvent(string eventId, string timing, Uid source)
    {
        Logger.LogEvent(eventId, timing, source);
        EventRegistry.GetEvent(timing, eventId)?.Apply(source, this);
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
}