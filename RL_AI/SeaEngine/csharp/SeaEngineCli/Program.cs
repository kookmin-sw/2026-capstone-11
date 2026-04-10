using System.Text.Json;
using System.Text.Json.Serialization;
using SeaEngine;
using SeaEngine.Actions;
using SeaEngine.CardManager;
using SeaEngine.GameDataManager.Components;
using SeaEngine.Logger;

var jsonOptions = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};

Game? game = null;

while (true)
{
    var line = Console.ReadLine();
    if (line == null) break;
    if (string.IsNullOrWhiteSpace(line)) continue;

    try
    {
        var request = JsonSerializer.Deserialize<BridgeRequest>(line, jsonOptions);
        if (request == null || string.IsNullOrWhiteSpace(request.Command))
        {
            WriteResponse(new BridgeResponse("error", null, "invalid_request"));
            continue;
        }

        switch (request.Command)
        {
            case "ping":
                WriteResponse(new BridgeResponse("ok", new { message = "pong" }, null));
                break;

            case "init":
                game = CreateGame(request);
                WriteResponse(new BridgeResponse("ok", BuildSnapshot(game), null));
                break;

            case "snapshot":
                EnsureGame(game);
                WriteResponse(new BridgeResponse("ok", BuildSnapshot(game!), null));
                break;

            case "apply":
                EnsureGame(game);
                if (string.IsNullOrWhiteSpace(request.ActionUid))
                {
                    throw new InvalidOperationException("action_uid is required");
                }

                var action = game!.Actions.FirstOrDefault(a => a.Guid.ToString() == request.ActionUid);
                if (action == null)
                {
                    throw new InvalidOperationException($"Unknown action uid: {request.ActionUid}");
                }

                game.UseAction(action.Guid);
                WriteResponse(new BridgeResponse("ok", BuildSnapshot(game), null));
                break;

            case "close":
                WriteResponse(new BridgeResponse("ok", new { closed = true }, null));
                return;

            default:
                WriteResponse(new BridgeResponse("error", null, $"unknown_command:{request.Command}"));
                break;
        }
    }
    catch (Exception ex)
    {
        WriteResponse(new BridgeResponse("error", null, ex.Message));
    }
}

return;

void WriteResponse(BridgeResponse response)
{
    Console.WriteLine(JsonSerializer.Serialize(response, jsonOptions));
    Console.Out.Flush();
}

Game CreateGame(BridgeRequest request)
{
    var cardsPath = string.IsNullOrWhiteSpace(request.CardDataPath)
        ? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "cards", "Cards.csv"))
        : Path.GetFullPath(request.CardDataPath);
    var loader = new CardLoader(cardsPath);
    var created = new Game(loader, new SilentLogger(), request.Player1Id ?? "P1", request.Player2Id ?? "P2");
    created.Init(request.Player1Deck ?? "", request.Player2Deck ?? "");
    return created;
}

static void EnsureGame(Game? existing)
{
    if (existing == null)
    {
        throw new InvalidOperationException("game_not_initialized");
    }
}

static object BuildSnapshot(Game game)
{
    var data = game.Data;
    return new
    {
        turn = data.Turn,
        active_player = data.ActivePlayerId,
        result = data.Result.ToString(),
        winner_id = data.WinnerId,
        players = new[]
        {
            BuildPlayer(data.Player1),
            BuildPlayer(data.Player2),
        },
        board = data.Board.Cards.Select(BuildCard).ToList(),
        actions = game.Actions.Select(BuildAction).ToList(),
    };
}

static object BuildPlayer(Player player)
{
    return new
    {
        id = player.Id,
        hand_count = player.Hand.Count,
        deck_count = player.Deck.Count,
        trash_count = player.Trash.Count,
        hand = player.Hand.Cards.Select(card => new
        {
            uid = card.Guid.ToString(),
            card_id = card.Data.Id,
            name = card.Data.Name,
        }).ToList(),
    };
}

static object BuildCard(Card card)
{
    return new
    {
        uid = card.Guid.ToString(),
        card_id = card.Data.Id,
        name = card.Data.Name,
        owner = card.Owner.Id,
        role = card.Data.UnitType.ToString(),
        atk = card.Unit.Atk,
        effective_atk = card.Unit.EffectiveAtk,
        hp = card.Unit.Hp,
        max_hp = card.Unit.MaxHp,
        is_placed = card.Unit.IsPlaced,
        is_moved = card.Unit.IsMoved,
        is_attacked = card.Unit.IsAttacked,
        pos_x = card.Unit.PosX,
        pos_y = card.Unit.PosY,
        statuses = card.Unit.Statuses.Select(status => new
        {
            type = status.Type.ToString(),
            value = status.Value,
            remaining_turns = status.RemainingTurns,
            source_key = status.SourceKey,
        }).ToList(),
    };
}

static object BuildAction(GameAction action)
{
    return new
    {
        uid = action.Guid.ToString(),
        effect_id = action.EffectId,
        source = action.Source.ToString(),
        target = new
        {
            type = action.Target.Type.ToString(),
            guid = action.Target.Guid.ToString(),
            guid2 = action.Target.Guid2.ToString(),
            pos_x = action.Target.PosX,
            pos_y = action.Target.PosY,
        },
        text = action.ToString(),
    };
}

file sealed record BridgeRequest(
    string? Command,
    string? CardDataPath = null,
    string? Player1Deck = null,
    string? Player2Deck = null,
    string? Player1Id = null,
    string? Player2Id = null,
    string? ActionUid = null
);

file sealed record BridgeResponse(string Status, object? Payload = null, string? Error = null);

file sealed class SilentLogger : ILogger
{
    public void Log(string message, GameAction action, SeaEngine.GameDataManager.GameData data)
    {
    }
}
