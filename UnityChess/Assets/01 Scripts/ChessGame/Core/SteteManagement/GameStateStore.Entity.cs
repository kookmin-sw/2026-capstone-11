using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Core.StateManagement
{
    public partial class GameStateStore
    {
        public void AddOrReplacePlayer(PlayerState player)
        {
            ValidatePlayerState(player);
            Players[player.playerId] = player;
        }

        public bool TryGetPlayer(string playerId, out PlayerState player)
        {
            if (string.IsNullOrWhiteSpace(playerId))
            {
                player = null;
                return false;
            }

            return Players.TryGetValue(playerId, out player);
        }

        public PlayerState GetPlayer(string playerId)
        {
            if (!TryGetPlayer(playerId, out var player))
                throw new KeyNotFoundException($"[GameStateStore] PlayerState 없음: {playerId}");

            return player;
        }

        public string TryGetPlayerId(int idx=0)
        {
            return Players.Keys.ToList()[idx];
        }

        // 세션에 접속한 플레이어의 ID가 Json의 P1과 일치하는지 여부로 로컬 플레이어가 P1인지 판단
        public bool IsLocalPlayer()
        {
            return string.Equals(LocalPlayerId, Players.Keys.First(), StringComparison.Ordinal);
        }


        public void AddOrReplaceUnit(EntityState state)
        {
            ValidateEntityState(state);
            Units[state.id] = state;
        }

        public bool TryGetUnit(EntityID id, out EntityState state)
        {
            return Units.TryGetValue(id, out state);
        }

        public EntityState GetUnit(EntityID id)
        {
            if (!Units.TryGetValue(id, out var state))
                throw new KeyNotFoundException($"[GameStateStore] EntityState 없음: {id}");

            return state;
        }

        public void SetMoved(EntityID id, bool isMoved)
        {
            var unit = GetUnit(id);
            unit.isMoved = isMoved;
        }

        public void SetUnitStats(EntityID id, int attack, int hp, int maxHp)
        {
            var unit = GetUnit(id);
            unit.curAttack = attack;
            unit.curHp = Mathf.Max(0, hp);
            unit.maxHp = Mathf.Max(0, maxHp);
        }

        public void AddBuff(EntityID unitId, EffectState effect)
        {
            if (effect == null)
                throw new ArgumentNullException(nameof(effect));

            var unit = GetUnit(unitId);
            unit.buffs ??= new List<EffectState>();

            if (unit.buffs.Exists(x => x.id.Equals(effect.id)))
                return;

            unit.buffs.Add(effect);
        }

        public bool RemoveBuff(EntityID unitId, string buffId)
        {
            var unit = GetUnit(unitId);
            var index = unit.buffs.FindIndex(x => string.Equals(x.id.id, buffId, StringComparison.Ordinal));
            if (index < 0)
                return false;

            unit.buffs.RemoveAt(index);
            return true;
        }

        public void ClearBuffs(EntityID unitId)
        {
            GetUnit(unitId).buffs.Clear();
        }
    }
}
