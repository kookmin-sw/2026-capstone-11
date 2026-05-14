using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using Core.DTO;
using ui.view;
using PlayFab.ClientModels;

namespace Core.StateManagement
{
    public partial class GameStateStore
    {
        private void ApplyActions(List<ActionDTO> actionDtos)
        {
            actions.Clear();
            actionsBySource.Clear();
            actionsBySourceAndCell.Clear();
            actionsBySourceAndTargetsKey.Clear();
            noTargetActionBySource.Clear();
            turnEndAction = null;

            if (actionDtos == null)
                return;

            foreach (var dto in actionDtos)
            {
                if (dto == null)
                    continue;

                var action = ParseAction(dto);
                actions.Add(action);

                if (action.effectType == RuntimeActionEffectType.TurnEnd)
                {
                    turnEndAction = action;
                }

                if (action.source.IsEmpty)
                    continue;

                if (!actionsBySource.TryGetValue(action.source, out var list))
                {
                    list = new List<RuntimeAction>();
                    actionsBySource[action.source] = list;
                }
                list.Add(action);

                if (action.targetType == RuntimeActionTargetType.Position && action.positionTarget.HasValue)
                {
                    if (!actionsBySourceAndCell.TryGetValue(action.source, out var map))
                    {
                        map = new Dictionary<Vector2Int, RuntimeAction>();
                        actionsBySourceAndCell[action.source] = map;
                    }

                    map[action.positionTarget.Value] = action;
                }
                else if (action.targetType == RuntimeActionTargetType.EntityList)
                {
                    if (!actionsBySourceAndTargetsKey.TryGetValue(action.source, out var map))
                    {
                        map = new Dictionary<string, RuntimeAction>(StringComparer.Ordinal);
                        actionsBySourceAndTargetsKey[action.source] = map;
                    }

                    map[MakeTargetsKey(action.entityTargets)] = action;
                }
                else if (action.targetType == RuntimeActionTargetType.None)
                {
                    noTargetActionBySource[action.source] = action;
                }
            }
        }

        public IReadOnlyList<RuntimeAction> GetActionsBySource(ActionSourceKey source)
        {
            if (source.IsEmpty)
                return Array.Empty<RuntimeAction>();

            return actionsBySource.TryGetValue(source, out var list)
                ? list
                : Array.Empty<RuntimeAction>();
        }

        public HashSet<string> GetSelectableSources()
        {
            return actionsBySource.Keys.Select(k => k.Uid).ToHashSet();
        }

        public HashSet<Vector2Int> GetSelectableCells(ActionSourceKey source)
        {
            if (source.IsEmpty)
                return new HashSet<Vector2Int>();

            if (!actionsBySourceAndCell.TryGetValue(source, out var map))
                return new HashSet<Vector2Int>();

            return map.Keys.ToHashSet();
        }

        public IReadOnlyList<IReadOnlyList<EntityID>> GetSelectableTargetEntityGroups(ActionSourceKey source)
        {
            if (source.IsEmpty)
                return Array.Empty<IReadOnlyList<EntityID>>();

            var actions = GetActionsBySource(source);
            var result = new List<IReadOnlyList<EntityID>>();

            foreach (var action in actions)
            {
                if (action.targetType != RuntimeActionTargetType.EntityList || action.entityTargets.Count == 0)
                    continue;

                result.Add(action.entityTargets);
            }

            return result;
        }

        public bool TryResolveNoTargetAction(ActionSourceKey source, out RuntimeAction action)
        {
            if (!source.IsEmpty &&
                noTargetActionBySource.TryGetValue(source, out action))
            {
                return true;
            }

            action = null;
            return false;
        }

        public bool TryResolveBySourceAndCell(ActionSourceKey source, Vector2Int pos, out RuntimeAction action)
        {
            if (!source.IsEmpty &&
                actionsBySourceAndCell.TryGetValue(source, out var map) &&
                map.TryGetValue(pos, out action))
            {
                return true;
            }

            action = null;
            return false;
        }

        public bool TryResolveBySourceAndTargets(ActionSourceKey source, IEnumerable<EntityID> targetIds, out RuntimeAction action)
        {
            action = null;

            if (source.IsEmpty)
                return false;

            if (!actionsBySourceAndTargetsKey.TryGetValue(source, out var map))
                return false;

            return map.TryGetValue(MakeTargetsKey(targetIds), out action);
        }

        public RuntimeAction GetTurnEndAction()
        {
            if (turnEndAction == null)
                throw new InvalidOperationException("[GameStateStore] TurnEnd action is missing.");

            return turnEndAction;
        }

        public bool HasAnyActionForSource(ActionSourceKey source)
        {
            return !source.IsEmpty && actionsBySource.ContainsKey(source);
        }

        public bool CanDeploy(ActionSourceKey source)
        {
            var availableActions = GetActionsBySource(source);
            return availableActions.Any(x => x.effectType == RuntimeActionEffectType.DeployUnit);
        }

        public bool CanUseEffect(ActionSourceKey source)
        {
            var availableActions = GetActionsBySource(source);
            return availableActions.Any(x => x.effectType == RuntimeActionEffectType.CardEffect);
        }

        private RuntimeAction ParseAction(ActionDTO dto)
        {
            var action = new RuntimeAction
            {
                uid = dto.Uid,
                effectId = dto.EffectId,
                effectType = ParseEffectType(dto.EffectId),
                source = new ActionSourceKey(ParseSourceType(dto.EffectId), dto.Source),
                rawTarget = dto.Target?.Value ?? string.Empty,
                targetType = RuntimeActionTargetType.None
            };

            ParseTarget(dto.Target, action);
            return action;
        }

        private RuntimeActionEffectType ParseEffectType(string effectId)
        {
            return effectId switch
            {
                "DefaultMove" => RuntimeActionEffectType.DefaultMove,
                "DeployUnit" => RuntimeActionEffectType.DeployUnit,
                "TurnEnd" => RuntimeActionEffectType.TurnEnd,
                "PawnGeneric" => RuntimeActionEffectType.PawnGeneric,
                null or "" => RuntimeActionEffectType.Unknown,
                _ => RuntimeActionEffectType.CardEffect
            };
        }

        private ViewType ParseSourceType(string effectId)
        {
            return effectId switch
            {
                "DefaultMove" => ViewType.Unit,
                "DeployUnit" => ViewType.Card,
                "TurnEnd" => ViewType.None,
                "PawnGeneric" => ViewType.Card,
                null or "" => ViewType.None,
                _ => ViewType.Card
            };
        }

        private void ParseTarget(ActionTargetDTO target, RuntimeAction action)
        {
            if (target == null || string.IsNullOrWhiteSpace(target.Type))
            {
                action.targetType = RuntimeActionTargetType.None;
                return;
            }

            var raw = target.Value ?? string.Empty;

            switch (target.Type)
            {
                case "None":
                    action.targetType = RuntimeActionTargetType.None;
                    return;

                case "Cell":
                    {
                        var parts = raw.Split('/');
                        if (parts.Length == 2 &&
                            int.TryParse(parts[0], out var x) &&
                            int.TryParse(parts[1], out var y))
                        {
                            action.targetType = RuntimeActionTargetType.Position;
                            action.positionTarget = new Vector2Int(x, y);
                            return;
                        }

                        action.targetType = RuntimeActionTargetType.None;
                        return;
                    }

                case "Target":
                case "TargetList":
                case "Entity":
                case "EntityList":
                default:
                    {
                        if (string.IsNullOrWhiteSpace(raw))
                        {
                            action.targetType = RuntimeActionTargetType.None;
                            return;
                        }

                        action.targetType = RuntimeActionTargetType.EntityList;
                        action.entityTargets = raw
                            .Split('/')
                            .Where(x => !string.IsNullOrWhiteSpace(x))
                            .Select(x => new EntityID(x))
                            .ToList();
                        return;
                    }
            }
        }
    }
}
