using System.Net;
using Grpc.Core;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using SeaEngine;
using SeaEngine.CardManager;
using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;
using SeaEngine.Logger;
using SeaEngine.Protos;
using System.Text.Json;

// Alias to resolve ambiguity
using ProtoPlayer = SeaEngine.Protos.Player;
using ProtoCard = SeaEngine.Protos.Card;
using ProtoAction = SeaEngine.Protos.GameAction;
using ProtoStatus = SeaEngine.Protos.Status;
using ProtoCardData = SeaEngine.Protos.CardData;
using EnginePlayer = SeaEngine.GameDataManager.Components.Player;
using EngineCard = SeaEngine.GameDataManager.Components.Card;
using EngineAction = SeaEngine.Common.GameAction;
using GrpcStatus = Grpc.Core.Status;

var builder = WebApplication.CreateBuilder(args);

// 로그 억제
builder.Logging.ClearProviders();
builder.Logging.SetMinimumLevel(Microsoft.Extensions.Logging.LogLevel.Error);

builder.Services.AddGrpc();

builder.WebHost.ConfigureKestrel(options =>
{
    options.Listen(IPAddress.Loopback, 0, listenOptions =>
    {
        listenOptions.Protocols = HttpProtocols.Http2;
    });
});

var app = builder.Build();
app.MapGrpcService<SeaEngineServiceImpl>();

// 서버 시작 전/후에 포트 정보를 확실히 노출
await app.StartAsync();

// 실제 할당된 포트 찾기
var address = app.Urls.FirstOrDefault();
if (address != null)
{
    var actualPort = address.Split(':').Last();
    Console.WriteLine($"PORT:{actualPort}");
    Console.Out.Flush();
}

await app.WaitForShutdownAsync();

public class SeaEngineServiceImpl : SeaEngineService.SeaEngineServiceBase
{
    private static Game? _game;
    private static int _turnCounter = 1;
    private static readonly object _lock = new();

    public override Task<PongResponse> Ping(Empty request, ServerCallContext context)
    {
        return Task.FromResult(new PongResponse { Message = "pong" });
    }

    public override Task<Snapshot> InitGame(InitRequest request, ServerCallContext context)
    {
        try
        {
            lock (_lock)
            {
                _game = CreateGame(request);
                _turnCounter = 1;
                return Task.FromResult(BuildSnapshot(_game, _turnCounter));
            }
        }
        catch (Exception ex)
        {
            throw new RpcException(new GrpcStatus(StatusCode.Internal, ex.ToString()));
        }
    }

    public override Task<Snapshot> ApplyAction(ActionRequest request, ServerCallContext context)
    {
        try
        {
            lock (_lock)
            {
                if (_game == null) throw new RpcException(new GrpcStatus(StatusCode.FailedPrecondition, "Game not initialized"));

                var action = _game.Actions.FirstOrDefault(a => a.Guid.ToString() == request.ActionUid);
                if (action == null) throw new RpcException(new GrpcStatus(StatusCode.NotFound, $"Unknown action uid: {request.ActionUid}"));

                try
                {
                    _game.UseAction(action.Guid);
                    if (action.EffectId == "TurnEnd")
                    {
                        _turnCounter += 1;
                    }
                }
                catch (Exception engineEx)
                {
                    Console.Error.WriteLine($"[Engine Logic Error] {engineEx.Message}");
                }
                
                return Task.FromResult(BuildSnapshot(_game, _turnCounter));
            }
        }
        catch (Exception ex)
        {
            if (ex is RpcException) throw;
            throw new RpcException(new GrpcStatus(StatusCode.Internal, ex.ToString()));
        }
    }

    public override Task<Snapshot> GetSnapshot(Empty request, ServerCallContext context)
    {
        lock (_lock)
        {
            if (_game == null) throw new RpcException(new GrpcStatus(StatusCode.FailedPrecondition, "Game not initialized"));
            return Task.FromResult(BuildSnapshot(_game, _turnCounter));
        }
    }

    private Game CreateGame(InitRequest request)
    {
        var cardsPath = string.IsNullOrWhiteSpace(request.CardDataPath)
            ? Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "cards", "Cards.csv"))
            : Path.GetFullPath(request.CardDataPath);
        var loader = new CardLoader(cardsPath);
        var created = new Game(loader, new SilentLogger(), request.Player1Id ?? "P1", request.Player2Id ?? "P2");
        created.Init(
            NormalizeDeckJson(request.Player1Deck, true),
            NormalizeDeckJson(request.Player2Deck, false)
        );
        return created;
    }

    private string NormalizeDeckJson(string? deckJson, bool player1)
    {
        if (!string.IsNullOrWhiteSpace(deckJson)) return deckJson;

        var fallback = player1
            ? new[] { "Or_L", "Or_B", "Or_N", "Or_R", "Or_P", "Or_P", "Or_P" }
            : new[] { "Cl_L", "Cl_B", "Cl_N", "Cl_R", "Cl_P", "Cl_P", "Cl_P" };
        return JsonSerializer.Serialize(fallback);
    }

    private Snapshot BuildSnapshot(Game game, int turnCounter)
    {
        var data = game.Data;
        var snapshot = new Snapshot
        {
            Turn = turnCounter,
            ActivePlayer = data.ActivePlayerId,
            Result = BuildResult(data),
            WinnerId = data.WinnerId
        };

        if (data.Player1 != null) snapshot.Players.Add(BuildPlayer(data.Player1));
        if (data.Player2 != null) snapshot.Players.Add(BuildPlayer(data.Player2));
        
        if (data.Board?.Cards != null)
        {
            foreach (var card in data.Board.Cards)
            {
                if (card != null) snapshot.Board.Add(BuildCard(card));
            }
        }

        if (game.Actions != null)
        {
            foreach (var action in game.Actions)
            {
                if (action != null) snapshot.Actions.Add(BuildAction(action));
            }
        }

        return snapshot;
    }

    private string BuildResult(SeaEngine.GameDataManager.GameData data)
    {
        if (data.Winner == null) return "Ongoing";
        return data.Winner.Id == data.Player1.Id ? "Player1Win" : "Player2Win";
    }

    private ProtoPlayer BuildPlayer(EnginePlayer player)
    {
        var p = new ProtoPlayer
        {
            Id = player.Id ?? "",
            HandCount = player.Hand?.Count ?? 0,
            DeckCount = player.Deck?.Count ?? 0,
            TrashCount = player.Trash?.Count ?? 0
        };
        
        if (player.Hand?.Cards != null)
        {
            foreach (var card in player.Hand.Cards)
            {
                if (card == null) continue;
                p.Hand.Add(new ProtoCardData
                {
                    Uid = card.Guid?.ToString() ?? "",
                    CardId = card.Data?.Id ?? "",
                    Name = card.Data?.Name ?? ""
                });
            }
        }
        return p;
    }

    private ProtoCard BuildCard(EngineCard card)
    {
        var buffs = card.Unit?.Buffs;
        var tempAtk = (buffs != null && buffs.TryGetValue("TempAtk", out var atkBuff)) ? atkBuff : 0;
        var effectiveAtk = (card.Unit?.Atk ?? 0) + tempAtk;

        var c = new ProtoCard
        {
            Uid = card.Guid?.ToString() ?? "",
            CardId = card.Data?.Id ?? "",
            Name = card.Data?.Name ?? "",
            Owner = card.Owner?.Id ?? "",
            Role = card.Data?.UnitType.ToString() ?? "",
            Atk = card.Unit?.Atk ?? 0,
            EffectiveAtk = effectiveAtk,
            Hp = card.Unit?.Hp ?? 0,
            MaxHp = card.Unit?.MaxHp ?? 0,
            IsPlaced = card.Unit?.IsPlaced ?? false,
            IsMoved = card.Unit?.IsMoved ?? false,
            IsAttacked = false,
            PosX = card.Unit?.PosX ?? -1,
            PosY = card.Unit?.PosY ?? -1
        };

        if (buffs != null)
        {
            foreach (var buff in buffs)
            {
                c.Statuses.Add(new ProtoStatus
                {
                    Type = buff.Key switch
                    {
                        "TempAtk" => "AttackModifier",
                        "CantMove" => "MoveLock",
                        _ => buff.Key
                    },
                    Value = buff.Value,
                    RemainingTurns = 1,
                    SourceKey = buff.Key
                });
            }
        }

        return c;
    }

    private ProtoAction BuildAction(EngineAction action)
    {
        return new ProtoAction
        {
            Uid = action.Guid?.ToString() ?? "",
            EffectId = action.EffectId ?? "",
            Source = action.Source?.ToString() ?? "",
            Target = action.Target == null ? null : new Target
            {
                Type = action.Target.Type.ToString(),
                Guid = action.Target.Guid?.ToString() ?? "",
                Guid2 = action.Target.Guid2?.ToString() ?? "",
                PosX = action.Target.PosX,
                PosY = action.Target.PosY
            },
            Text = action.ToString() ?? ""
        };
    }
}

file sealed class SilentLogger : SeaEngine.Logger.ILogger
{
    public void Log(string message, EngineAction action, SeaEngine.GameDataManager.GameData data)
    {
    }
}
