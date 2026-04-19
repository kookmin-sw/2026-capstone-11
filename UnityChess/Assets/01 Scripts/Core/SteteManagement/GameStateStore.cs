using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Newtonsoft.Json;
using Core.DTO;

namespace Core.StateManagement
{
    /// <summary>
    /// 게임 내 엔티티의 UUID
    /// </summary>
    [Serializable]
    public readonly struct EntityID : IEquatable<EntityID>
    {
        public readonly string id;

        public EntityID(string id)
        {
            this.id = id ?? string.Empty;
        }

        public bool IsEmpty => string.IsNullOrWhiteSpace(id);

        public bool Equals(EntityID other)
        {
            return string.Equals(id, other.id, StringComparison.Ordinal);
        }

        public override bool Equals(object obj)
        {
            return obj is EntityID other && Equals(other);
        }

        public override int GetHashCode()
        {
            return StringComparer.Ordinal.GetHashCode(id ?? string.Empty);
        }

        public override string ToString()
        {
            return id ?? string.Empty;
        }

        public static implicit operator string(EntityID value) => value.id;
        public static implicit operator EntityID(string value) => new EntityID(value);
    }

    /// <summary>
    /// 게임 내 엔티티에 적용된 버프/디버프
    /// </summary>
    [Serializable]
    public class EffectState
    {
        public EntityID id;
        public int value;
        public int duration;
    }

    /// <summary>
    /// 게임의 전체 상태를 표현하는 클래스
    /// </summary>
    [Serializable]
    public class EntityState
    {
        public EntityID id;
        public string cardId;
        public string owner;
        public bool isPlaced;
        public bool isMoved;
        public int curAttack;
        public int curHp;
        public int maxHp;
        public Vector2Int position;
        public List<EffectState> buffs = new();

        public EntityState() { }

        public EntityState(
            EntityID id,
            string cardId,
            string owner,
            bool isPlaced,
            bool isMoved,
            Vector2Int position,
            int curAttack,
            int curHp,
            int maxHp,
            List<EffectState> buffs = null)
        {
            this.id = id;
            this.cardId = cardId;
            this.owner = owner;
            this.isPlaced = isPlaced;
            this.isMoved = isMoved;
            this.position = position;
            this.curAttack = curAttack;
            this.curHp = curHp;
            this.maxHp = maxHp;
            this.buffs = buffs ?? new List<EffectState>();
        }
    }

    /// <summary>
    /// 플레이어의 상태를 표현하는 클래스
    /// </summary>
    [Serializable]
    public class PlayerState
    {
        public string playerId;
        public List<EntityID> hand = new();
        public List<EntityID> deck = new();
        public List<EntityID> trash = new();
        public List<EntityID> board = new();

        public PlayerState() { }

        public PlayerState(string playerId)
        {
            this.playerId = playerId;
        }
    }

    public enum RuntimeActionEffectType
    {
        CardEffect,
        DefaultMove,
        DeployUnit,
        TurnEnd,
        PawnGeneric,
        Unknown
    }

    public enum RuntimeActionTargetType
    {
        None,
        Position,
        EntityList
    }

    /// <summary>
    /// 플레이어가 선택할 수 있는 행동을 표현하는 클래스
    /// </summary>
    [Serializable]
    public class RuntimeAction
    {
        public string uid;
        public string effectId;
        public RuntimeActionEffectType effectType;
        public string source;
        public string rawTarget;
        public RuntimeActionTargetType targetType = RuntimeActionTargetType.None;
        public Vector2Int? positionTarget;
        public List<EntityID> entityTargets = new();

        public bool HasNoTarget => targetType == RuntimeActionTargetType.None;
    }

    /// <summary>
    /// 게임 상태의 단일 진실 원천
    /// </summary>
    public partial class GameStateStore : MonoBehaviour
    {
        // 상태 저장 데이터 구조
        public Dictionary<EntityID, EntityState> Units { get; private set; } = new();
        public Dictionary<string, PlayerState> Players { get; private set; } = new(StringComparer.Ordinal);
        public Dictionary<Vector2Int, EntityID> BoardIndex { get; private set; } = new();

        public int TurnNumber { get; private set; }
        public string ActivePlayerId { get; private set; } = string.Empty;

        // Action 인덱스
        private readonly List<RuntimeAction> actions = new();
        private readonly Dictionary<string, List<RuntimeAction>> actionsBySource = new(StringComparer.Ordinal);
        private readonly Dictionary<string, Dictionary<Vector2Int, RuntimeAction>> actionsBySourceAndCell = new(StringComparer.Ordinal);
        private readonly Dictionary<string, Dictionary<string, RuntimeAction>> actionsBySourceAndTargetsKey = new(StringComparer.Ordinal);
        private readonly Dictionary<string, RuntimeAction> noTargetActionBySource = new(StringComparer.Ordinal);
        private RuntimeAction turnEndAction;

        // 게임 상태를 초기화
        public void ResetStore()
        {
            Units.Clear();
            Players.Clear();
            BoardIndex.Clear();

            actions.Clear();
            actionsBySource.Clear();
            actionsBySourceAndCell.Clear();
            actionsBySourceAndTargetsKey.Clear();
            noTargetActionBySource.Clear();
            turnEndAction = null;

            TurnNumber = 0;
            ActivePlayerId = string.Empty;
        }
        
        // 게임 상태를 JSON 스냅샷으로부터 적용
        public void ApplySnapshotJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
                throw new ArgumentException("snapshot json is empty", nameof(json));

            var dto = JsonConvert.DeserializeObject<GameSnapshotDTO>(json);
            if (dto == null)
                throw new InvalidOperationException("[GameStateStore] snapshot json deserialize failed.");

            ApplySnapshot(dto);
        }

        public void ApplySnapshot(GameSnapshotDTO snapshot)
        {
            if (snapshot == null)
                throw new ArgumentNullException(nameof(snapshot));

            if (snapshot.Data == null)
                throw new InvalidOperationException("[GameStateStore] snapshot.Data is null");

            ResetStore();

            ApplyPlayers(snapshot.Data);
            ApplyEntities(snapshot.Data.Board);
            RebuildPlayerBoardLists();
            RebuildBoardIndex();

            ActivePlayerId = snapshot.Data.ActivePlayerId ?? string.Empty;

            ApplyActions(snapshot.Actions);
        }

        private void ApplyPlayers(GameSnapshotDataDTO data)
        {
            AddOrReplacePlayer(new PlayerState(data.Player1?.Id ?? "Player1")
            {
                hand = ToEntityIdList(data.Player1?.Hand),
                deck = ToEntityIdList(data.Player1?.Deck),
                trash = ToEntityIdList(data.Player1?.Trash)
            });

            AddOrReplacePlayer(new PlayerState(data.Player2?.Id ?? "Player2")
            {
                hand = ToEntityIdList(data.Player2?.Hand),
                deck = ToEntityIdList(data.Player2?.Deck),
                trash = ToEntityIdList(data.Player2?.Trash)
            });
        }

        private void ApplyEntities(List<BoardEntityDTO> boardDtos)
        {
            if (boardDtos == null)
                return;

            foreach (var dto in boardDtos)
            {
                if (dto == null)
                    continue;

                var state = new EntityState(
                    id: dto.Uid,
                    cardId: dto.Id,
                    owner: dto.Owner,
                    isPlaced: dto.IsPlaced,
                    isMoved: dto.IsMoved,
                    position: new Vector2Int(dto.X, dto.Y),
                    curAttack: dto.Atk,
                    curHp: dto.Hp,
                    maxHp: dto.MaxHp,
                    buffs: ConvertBuffs(dto.Buff)
                );

                AddOrReplaceUnit(state);
            }
        }

        // 게임 상태에 행동 인덱스 적용
        private List<EntityID> ToEntityIdList(List<string> src)
        {
            if (src == null)
                return new List<EntityID>();

            return src
                .Where(x => !string.IsNullOrWhiteSpace(x))
                .Select(x => new EntityID(x))
                .ToList();
        }

        private List<EffectState> ConvertBuffs(List<BuffDTO> src)
        {
            if (src == null || src.Count == 0)
                return new List<EffectState>();

            var result = new List<EffectState>(src.Count);

            foreach (var buff in src)
            {
                if (buff == null)
                    continue;

                result.Add(new EffectState
                {
                    id = new EntityID(buff.Id),
                    value = buff.Value,
                    duration = buff.Duration
                });
            }

            return result;
        }

        private string MakeTargetsKey(IEnumerable<EntityID> targetIds)
        {
            if (targetIds == null)
                return string.Empty;

            return string.Join("/",
                targetIds
                    .Select(x => x.id)
                    .Where(x => !string.IsNullOrWhiteSpace(x))
                    .OrderBy(x => x, StringComparer.Ordinal));
        }

        private void ValidatePlayerState(PlayerState player)
        {
            if (player == null)
                throw new ArgumentNullException(nameof(player));

            if (string.IsNullOrWhiteSpace(player.playerId))
                throw new ArgumentException("playerId is empty", nameof(player));

            player.hand ??= new List<EntityID>();
            player.deck ??= new List<EntityID>();
            player.trash ??= new List<EntityID>();
            player.board ??= new List<EntityID>();
        }

        private void ValidateEntityState(EntityState state)
        {
            if (state == null)
                throw new ArgumentNullException(nameof(state));

            if (state.id.IsEmpty)
                throw new ArgumentException("entity id is empty", nameof(state));

            if (string.IsNullOrWhiteSpace(state.cardId))
                throw new ArgumentException("cardId is empty", nameof(state));

            if (string.IsNullOrWhiteSpace(state.owner))
                throw new ArgumentException("owner is empty", nameof(state));

            // 일부 게임 상황에서 이부분이 오류를 일으킴
            // if (state.curHp < 0)
            //     throw new ArgumentException("curHp must be >= 0", nameof(state));

            if (state.maxHp < 0)
                throw new ArgumentException("maxHp must be >= 0", nameof(state));

            if (state.curHp > state.maxHp)
                throw new ArgumentException("curHp cannot exceed maxHp", nameof(state));

            state.buffs ??= new List<EffectState>();
        }
    }
}
