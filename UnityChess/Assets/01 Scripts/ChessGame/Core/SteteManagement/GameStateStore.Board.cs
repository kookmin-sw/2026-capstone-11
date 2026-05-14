using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace Core.StateManagement
{
    public partial class GameStateStore
    {
        public void RebuildBoardIndex()
        {
            BoardIndex.Clear();

            foreach (var unit in Units.Values)
            {
                if (!unit.isPlaced)
                    continue;

                BoardIndex[unit.position] = unit.id;
            }
        }

        public void RebuildPlayerBoardLists()
        {
            foreach (var player in Players.Values)
            {
                player.board.Clear();
            }

            foreach (var unit in Units.Values)
            {
                if (!unit.isPlaced)
                    continue;

                if (Players.TryGetValue(unit.owner, out var player))
                {
                    player.board.Add(unit.id);
                }
            }
        }

        public IReadOnlyList<EntityID> GetHand(string playerId) => GetPlayer(playerId).hand;
        public IReadOnlyList<EntityID> GetDeck(string playerId) => GetPlayer(playerId).deck;
        public IReadOnlyList<EntityID> GetTrash(string playerId) => GetPlayer(playerId).trash;
        public IReadOnlyList<EntityID> GetBoard(string playerId) => GetPlayer(playerId).board;

        public bool IsPlaced(EntityID id) => GetUnit(id).isPlaced;
        public bool IsMoved(EntityID id) => GetUnit(id).isMoved;

        public void SetUnitPosition(EntityID id, Vector2Int pos, bool isPlaced)
        {
            var unit = GetUnit(id);
            unit.position = pos;
            unit.isPlaced = isPlaced;
            RebuildBoardIndex();
            RebuildPlayerBoardLists();
        }

        public void MoveUnit(EntityID id, Vector2Int pos)
        {
            var unit = GetUnit(id);
            unit.position = pos;
            unit.isPlaced = true;
            RebuildBoardIndex();
            RebuildPlayerBoardLists();
        }

        public bool TryGetUnitAt(Vector2Int pos, out EntityState unit)
        {
            if (BoardIndex.TryGetValue(pos, out var id) && Units.TryGetValue(id, out unit))
                return true;

            unit = null;
            return false;
        }

        public bool IsOccupied(Vector2Int pos)
        {
            return BoardIndex.ContainsKey(pos);
        }

        public IReadOnlyList<EntityState> GetPlacedUnits()
        {
            return Units.Values.Where(x => x.isPlaced).ToList();
        }

        public IReadOnlyList<EntityState> GetPlacedUnits(string ownerId)
        {
            return Units.Values
                .Where(x => x.isPlaced && string.Equals(x.owner, ownerId, StringComparison.Ordinal))
                .ToList();
        }
    }
}
