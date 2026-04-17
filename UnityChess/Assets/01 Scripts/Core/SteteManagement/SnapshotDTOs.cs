using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace Core.DTO
{
    [Serializable]
    public class GameSnapshotDTO
    {
        [JsonProperty("Data")]
        public GameSnapshotDataDTO Data;

        [JsonProperty("Actions")]
        public List<ActionDTO> Actions;
    }

    [Serializable]
    public class GameSnapshotDataDTO
    {
        [JsonProperty("Player1")]
        public PlayerSnapshotDTO Player1;

        [JsonProperty("Player2")]
        public PlayerSnapshotDTO Player2;

        [JsonProperty("Board")]
        public List<BoardEntityDTO> Board;

        [JsonProperty("ActivePlayerId")]
        public string ActivePlayerId;
    }

    [Serializable]
    public class PlayerSnapshotDTO
    {
        [JsonProperty("Id")]
        public string Id;

        [JsonProperty("Hand")]
        public List<string> Hand;

        [JsonProperty("Deck")]
        public List<string> Deck;

        [JsonProperty("Trash")]
        public List<string> Trash;
    }

    [Serializable]
    public class BoardEntityDTO
    {
        [JsonProperty("Uid")]
        public string Uid;

        [JsonProperty("Id")]
        public string Id;

        [JsonProperty("Owner")]
        public string Owner;

        [JsonProperty("isPlaced")]
        public bool IsPlaced;

        [JsonProperty("isMoved")]
        public bool IsMoved;

        [JsonProperty("X")]
        public int X;

        [JsonProperty("Y")]
        public int Y;

        [JsonProperty("Atk")]
        public int Atk;

        [JsonProperty("Hp")]
        public int Hp;

        [JsonProperty("MaxHp")]
        public int MaxHp;

        [JsonProperty("Buff")]
        public List<BuffDTO> Buff;
    }

    [Serializable]
    public class BuffDTO
    {
        [JsonProperty("Id")]
        public string Id;

        [JsonProperty("Value")]
        public int Value;

        [JsonProperty("Duration")]
        public int Duration;
    }

    [Serializable]
    public class ActionDTO
    {
        [JsonProperty("Uid")]
        public string Uid;

        [JsonProperty("EffectId")]
        public string EffectId;

        [JsonProperty("Source")]
        public string Source;

        [JsonProperty("Target")]
        public ActionTargetDTO Target;
    }

    [Serializable]
    public class ActionTargetDTO
    {
        [JsonProperty("Type")]
        public string Type;

        [JsonProperty("Value")]
        public string Value;
    }
}
