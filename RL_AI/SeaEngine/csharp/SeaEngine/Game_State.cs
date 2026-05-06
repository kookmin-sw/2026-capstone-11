using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading;
using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;

namespace SeaEngine;

public partial class Game
{
    private const int SnapshotVersion = 1;
    private static int _nextStateHandle;
    private static readonly Dictionary<int, CachedSnapshot> StateCache = [];
    private static readonly object StateCacheLock = new();

    public string CaptureState()
    {
        return Convert.ToBase64String(CaptureSnapshotBytes());
    }

    public byte[] CaptureSnapshotBytes()
    {
        var snapshot = CaptureSnapshot();
        return SerializeSnapshot(snapshot);
    }

    public int CaptureStateHandle()
    {
        var snapshot = CaptureSnapshot();
        return StoreSnapshot(SerializeSnapshot(snapshot), snapshot.TurnCounter);
    }

    private static byte[] SerializeSnapshot(BinaryGameSnapshot snapshot)
    {
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream, Encoding.UTF8, leaveOpen: true);
        WriteSnapshot(writer, snapshot);
        writer.Flush();
        return stream.ToArray();
    }

    public int StoreState(string snapshotToken)
    {
        return StoreState(Convert.FromBase64String(snapshotToken));
    }

    public int StoreState(byte[] snapshotBytes)
    {
        var snapshot = ReadSnapshot(snapshotBytes);
        return StoreSnapshot(snapshotBytes, snapshot.TurnCounter);
    }

    public void RestoreStateHandle(int handle)
    {
        RestoreSnapshotBytes(GetCachedSnapshot(handle).Bytes);
    }

    public int GetStateHandleTurnCounter(int handle)
    {
        return GetCachedSnapshot(handle).TurnCounter;
    }

    public void ReleaseStateHandle(int handle)
    {
        lock (StateCacheLock)
        {
            StateCache.Remove(handle);
        }
    }

    public static void ClearStateCache()
    {
        lock (StateCacheLock)
        {
            StateCache.Clear();
        }
    }

    public void RestoreState(string snapshotToken)
    {
        RestoreSnapshotBytes(Convert.FromBase64String(snapshotToken));
    }

    public void RestoreSnapshotBytes(byte[] snapshotBytes)
    {
        var snapshot = ReadSnapshot(snapshotBytes);
        RestoreSnapshot(snapshot);
    }

    public Game Fork()
    {
        var fork = new Game(CardLoader, Logger, Data.Player1.Id, Data.Player2.Id);
        fork.RestoreSnapshotBytes(CaptureSnapshotBytes());
        return fork;
    }

    public Game Clone()
    {
        return Fork();
    }

    private BinaryGameSnapshot CaptureSnapshot()
    {
        return new BinaryGameSnapshot
        {
            Player1Id = Data.Player1.Id,
            Player2Id = Data.Player2.Id,
            ActivePlayerId = Data.ActivePlayer.Id,
            WinnerId = Data.Winner?.Id ?? "",
            TurnCounter = Data.TurnCnt,
            Cards = Data.Board.Cards.Select(CaptureCard).ToList(),
            Player1Deck = Data.Player1.Deck.Cards.Select(c => c.Guid.ToString()).ToList(),
            Player1Hand = Data.Player1.Hand.Cards.Select(c => c.Guid.ToString()).ToList(),
            Player1Trash = Data.Player1.Trash.Cards.Select(c => c.Guid.ToString()).ToList(),
            Player2Deck = Data.Player2.Deck.Cards.Select(c => c.Guid.ToString()).ToList(),
            Player2Hand = Data.Player2.Hand.Cards.Select(c => c.Guid.ToString()).ToList(),
            Player2Trash = Data.Player2.Trash.Cards.Select(c => c.Guid.ToString()).ToList(),
        };
    }

    private static void WriteSnapshot(BinaryWriter writer, BinaryGameSnapshot snapshot)
    {
        writer.Write(SnapshotVersion);
        WriteString(writer, snapshot.Player1Id);
        WriteString(writer, snapshot.Player2Id);
        WriteString(writer, snapshot.ActivePlayerId);
        WriteString(writer, snapshot.WinnerId);
        writer.Write(snapshot.TurnCounter);

        writer.Write(snapshot.Cards.Count);
        foreach (var card in snapshot.Cards)
        {
            WriteCard(writer, card);
        }

        WriteStringList(writer, snapshot.Player1Deck);
        WriteStringList(writer, snapshot.Player1Hand);
        WriteStringList(writer, snapshot.Player1Trash);
        WriteStringList(writer, snapshot.Player2Deck);
        WriteStringList(writer, snapshot.Player2Hand);
        WriteStringList(writer, snapshot.Player2Trash);
    }

    private static BinaryGameSnapshot ReadSnapshot(byte[] snapshotBytes)
    {
        using var stream = new MemoryStream(snapshotBytes);
        using var reader = new BinaryReader(stream, Encoding.UTF8, leaveOpen: true);

        var version = reader.ReadInt32();
        if (version != SnapshotVersion)
        {
            throw new InvalidOperationException($"Unsupported SeaEngine snapshot version: {version}");
        }

        var snapshot = new BinaryGameSnapshot
        {
            Player1Id = ReadString(reader),
            Player2Id = ReadString(reader),
            ActivePlayerId = ReadString(reader),
            WinnerId = ReadString(reader),
            TurnCounter = reader.ReadInt32(),
        };

        var cardCount = reader.ReadInt32();
        for (var i = 0; i < cardCount; i++)
        {
            snapshot.Cards.Add(ReadCard(reader));
        }

        snapshot.Player1Deck = ReadStringList(reader);
        snapshot.Player1Hand = ReadStringList(reader);
        snapshot.Player1Trash = ReadStringList(reader);
        snapshot.Player2Deck = ReadStringList(reader);
        snapshot.Player2Hand = ReadStringList(reader);
        snapshot.Player2Trash = ReadStringList(reader);
        return snapshot;
    }

    private void RestoreSnapshot(BinaryGameSnapshot snapshot)
    {
        Data.Board.Clear();
        Data.Player1.Deck.Clear();
        Data.Player1.Hand.Clear();
        Data.Player1.Trash.Clear();
        Data.Player2.Deck.Clear();
        Data.Player2.Hand.Clear();
        Data.Player2.Trash.Clear();

        var cardUidFactory = new UidFactory("C");
        var cardsByUid = new Dictionary<string, Card>();
        foreach (var cardState in snapshot.Cards)
        {
            var owner = cardState.OwnerId == Data.Player2.Id ? Data.Player2 : Data.Player1;
            var card = new Card(CardLoader.GetCard(cardState.CardId), owner, cardUidFactory);
            RestoreCard(card, cardState);
            Data.Board.Register(card);
            cardsByUid[cardState.Uid] = card;
        }

        RestoreZone(Data.Player1.Deck, snapshot.Player1Deck, cardsByUid);
        RestoreZone(Data.Player1.Hand, snapshot.Player1Hand, cardsByUid);
        RestoreZone(Data.Player1.Trash, snapshot.Player1Trash, cardsByUid);
        RestoreZone(Data.Player2.Deck, snapshot.Player2Deck, cardsByUid);
        RestoreZone(Data.Player2.Hand, snapshot.Player2Hand, cardsByUid);
        RestoreZone(Data.Player2.Trash, snapshot.Player2Trash, cardsByUid);

        Data.ActivePlayer = snapshot.ActivePlayerId == Data.Player2.Id ? Data.Player2 : Data.Player1;
        Data.Winner = snapshot.WinnerId == Data.Player1.Id
            ? Data.Player1
            : snapshot.WinnerId == Data.Player2.Id
                ? Data.Player2
                : null;
        Data.TurnCnt = snapshot.TurnCounter;
        UpdateActions();
    }

    private static int StoreSnapshot(byte[] snapshotBytes, int turnCounter)
    {
        var handle = Interlocked.Increment(ref _nextStateHandle);
        lock (StateCacheLock)
        {
            StateCache[handle] = new CachedSnapshot(snapshotBytes, turnCounter);
        }
        return handle;
    }

    private static CachedSnapshot GetCachedSnapshot(int handle)
    {
        lock (StateCacheLock)
        {
            if (!StateCache.TryGetValue(handle, out var snapshot))
            {
                throw new KeyNotFoundException($"Unknown SeaEngine state handle: {handle}");
            }
            return snapshot;
        }
    }

    private static void WriteCard(BinaryWriter writer, BinaryCardState card)
    {
        WriteString(writer, card.Uid);
        WriteString(writer, card.CardId);
        WriteString(writer, card.OwnerId);
        writer.Write(card.IsPlaced);
        writer.Write(card.IsMoved);
        writer.Write(card.PosX);
        writer.Write(card.PosY);
        writer.Write(card.Atk);
        writer.Write(card.Hp);
        writer.Write(card.MaxHp);
        writer.Write(card.Buffs.Count);
        foreach (var buff in card.Buffs)
        {
            WriteString(writer, buff.Key);
            writer.Write(buff.Value);
        }
    }

    private static BinaryCardState ReadCard(BinaryReader reader)
    {
        var card = new BinaryCardState
        {
            Uid = ReadString(reader),
            CardId = ReadString(reader),
            OwnerId = ReadString(reader),
            IsPlaced = reader.ReadBoolean(),
            IsMoved = reader.ReadBoolean(),
            PosX = reader.ReadInt32(),
            PosY = reader.ReadInt32(),
            Atk = reader.ReadInt32(),
            Hp = reader.ReadInt32(),
            MaxHp = reader.ReadInt32(),
        };

        var buffCount = reader.ReadInt32();
        for (var i = 0; i < buffCount; i++)
        {
            card.Buffs[ReadString(reader)] = reader.ReadInt32();
        }

        return card;
    }

    private static void WriteStringList(BinaryWriter writer, IReadOnlyList<string> values)
    {
        writer.Write(values.Count);
        foreach (var value in values)
        {
            WriteString(writer, value);
        }
    }

    private static List<string> ReadStringList(BinaryReader reader)
    {
        var count = reader.ReadInt32();
        var values = new List<string>(Math.Max(0, count));
        for (var i = 0; i < count; i++)
        {
            values.Add(ReadString(reader));
        }
        return values;
    }

    private static void WriteString(BinaryWriter writer, string value)
    {
        writer.Write(value ?? string.Empty);
    }

    private static string ReadString(BinaryReader reader)
    {
        return reader.ReadString();
    }

    private static void RestoreCard(Card card, BinaryCardState state)
    {
        card.Unit.IsPlaced = state.IsPlaced;
        card.Unit.IsMoved = state.IsMoved;
        card.Unit.PosX = state.PosX;
        card.Unit.PosY = state.PosY;
        card.Unit.Atk = state.Atk;
        card.Unit.Hp = state.Hp;
        card.Unit.MaxHp = state.MaxHp;
        card.Unit.Buffs.Clear();
        foreach (var buff in state.Buffs)
        {
            card.Unit.Buffs[buff.Key] = buff.Value;
        }
    }

    private static BinaryCardState CaptureCard(Card card)
    {
        return new BinaryCardState
        {
            Uid = card.Guid.ToString(),
            CardId = card.Data.Id,
            OwnerId = card.Owner.Id,
            IsPlaced = card.Unit.IsPlaced,
            IsMoved = card.Unit.IsMoved,
            PosX = card.Unit.PosX,
            PosY = card.Unit.PosY,
            Atk = card.Unit.Atk,
            Hp = card.Unit.Hp,
            MaxHp = card.Unit.MaxHp,
            Buffs = new Dictionary<string, int>(card.Unit.Buffs),
        };
    }

    private static void RestoreZone(CardZone zone, IEnumerable<string> oldUids, IReadOnlyDictionary<string, Card> cardsByUid)
    {
        foreach (var oldUid in oldUids)
        {
            if (cardsByUid.TryGetValue(oldUid, out var card))
            {
                zone.AddCard(card);
            }
        }
    }

    private sealed class CachedSnapshot(byte[] bytes, int turnCounter)
    {
        public byte[] Bytes { get; } = bytes;
        public int TurnCounter { get; } = turnCounter;
    }

    private sealed class BinaryGameSnapshot
    {
        public string Player1Id { get; set; } = "Player1";
        public string Player2Id { get; set; } = "Player2";
        public string ActivePlayerId { get; set; } = "Player1";
        public string WinnerId { get; set; } = "";
        public int TurnCounter { get; set; }
        public List<BinaryCardState> Cards { get; set; } = [];
        public List<string> Player1Deck { get; set; } = [];
        public List<string> Player1Hand { get; set; } = [];
        public List<string> Player1Trash { get; set; } = [];
        public List<string> Player2Deck { get; set; } = [];
        public List<string> Player2Hand { get; set; } = [];
        public List<string> Player2Trash { get; set; } = [];
    }

    private sealed class BinaryCardState
    {
        public string Uid { get; set; } = "";
        public string CardId { get; set; } = "";
        public string OwnerId { get; set; } = "";
        public bool IsPlaced { get; set; }
        public bool IsMoved { get; set; }
        public int PosX { get; set; } = -1;
        public int PosY { get; set; } = -1;
        public int Atk { get; set; }
        public int Hp { get; set; }
        public int MaxHp { get; set; }
        public Dictionary<string, int> Buffs { get; set; } = [];
    }
}
