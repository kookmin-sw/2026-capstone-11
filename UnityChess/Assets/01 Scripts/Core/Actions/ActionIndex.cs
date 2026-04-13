using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace core.actions
{
    /// <summary>
    /// 파싱된 액션들을 source / target 기준으로 조회하는 인덱스
    /// </summary>
    public class ActionIndex
    {
        private readonly List<ParsedAction> all = new();

        // source -> actions
        private readonly Dictionary<string, List<ParsedAction>> bySource = new();

        // source -> cell -> action
        private readonly Dictionary<string, Dictionary<Vector2Int, ParsedAction>> bySourceAndCell = new();

        // source -> no-target action
        private readonly Dictionary<string, ParsedAction> bySourceNoTarget = new();

        // turn end
        private ParsedAction turnEndAction;

        public void SetActions(IEnumerable<ParsedAction> actions)
        {
            all.Clear();
            bySource.Clear();
            bySourceAndCell.Clear();
            bySourceNoTarget.Clear();
            turnEndAction = null;

            foreach (var action in actions)
            {
                all.Add(action);

                if (action.EffectType == ActionEffectType.TurnEnd)
                {
                    turnEndAction = action;
                }

                if (!string.IsNullOrEmpty(action.Source))
                {
                    if (!bySource.TryGetValue(action.Source, out var list))
                    {
                        list = new List<ParsedAction>();
                        bySource[action.Source] = list;
                    }
                    list.Add(action);
                }

                if (!string.IsNullOrEmpty(action.Source))
                {
                    if (action.TargetType == ParsedTargetType.Position && action.PositionTarget.HasValue)
                    {
                        if (!bySourceAndCell.TryGetValue(action.Source, out var cellMap))
                        {
                            cellMap = new Dictionary<Vector2Int, ParsedAction>();
                            bySourceAndCell[action.Source] = cellMap;
                        }

                        cellMap[action.PositionTarget.Value] = action;
                    }
                    else if (action.TargetType == ParsedTargetType.None)
                    {
                        bySourceNoTarget[action.Source] = action;
                    }
                }
            }
        }

        public IReadOnlyList<ParsedAction> GetAll()
        {
            return all;
        }

        public IReadOnlyList<ParsedAction> GetBySource(string sourceUid)
        {
            if (string.IsNullOrEmpty(sourceUid))
                return System.Array.Empty<ParsedAction>();

            if (bySource.TryGetValue(sourceUid, out var list))
                return list;

            return System.Array.Empty<ParsedAction>();
        }

        public HashSet<string> GetSelectableSources()
        {
            return bySource.Keys.ToHashSet();
        }

        public HashSet<Vector2Int> GetSelectableCells(string sourceUid)
        {
            if (string.IsNullOrEmpty(sourceUid))
                return new HashSet<Vector2Int>();

            if (bySourceAndCell.TryGetValue(sourceUid, out var map))
                return map.Keys.ToHashSet();

            return new HashSet<Vector2Int>();
        }

        public bool TryResolveNoTargetAction(string sourceUid, out ParsedAction action)
        {
            if (!string.IsNullOrEmpty(sourceUid) &&
                bySourceNoTarget.TryGetValue(sourceUid, out action))
            {
                return true;
            }

            action = null;
            return false;
        }

        public bool TryResolveBySourceAndCell(string sourceUid, Vector2Int pos, out ParsedAction action)
        {
            if (!string.IsNullOrEmpty(sourceUid) &&
                bySourceAndCell.TryGetValue(sourceUid, out var cellMap) &&
                cellMap.TryGetValue(pos, out action))
            {
                return true;
            }

            action = null;
            return false;
        }

        public bool TryGetTurnEndAction(out ParsedAction action)
        {
            action = turnEndAction;
            return action != null;
        }

        public bool HasAnyActionForSource(string sourceUid)
        {
            return !string.IsNullOrEmpty(sourceUid) && bySource.ContainsKey(sourceUid);
        }

        public bool HasOnlyCellTargets(string sourceUid)
        {
            var actions = GetBySource(sourceUid);
            if (actions.Count == 0) return false;

            return actions.All(a => a.TargetType == ParsedTargetType.Position);
        }

        public bool HasSingleNoTargetAction(string sourceUid)
        {
            var actions = GetBySource(sourceUid);
            return actions.Count == 1 && actions[0].TargetType == ParsedTargetType.None;
        }
    }
}