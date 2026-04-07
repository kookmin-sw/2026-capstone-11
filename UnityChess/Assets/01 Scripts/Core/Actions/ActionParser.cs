using System;
using UnityEngine;

namespace core.actions
{
    public static class ActionParser
    {
        public static ParsedAction Parse(ActionDTO dto)
        {
            var action = new ParsedAction
            {
                UID = dto.UID,
                EffectID = dto.EffectID,
                EffectType = ParseEffectType(dto.EffectID),
                Source = dto.Source,
                RawTarget = dto.Target,
                TargetType = ParsedTargetType.None
            };

            ParseTarget(dto.Target, action);

            return action;
        }

        private static ActionEffectType ParseEffectType(string effectId)
        {
            return effectId switch
            {
                "DefaultMove" => ActionEffectType.DefaultMove,
                "DeployUnit" => ActionEffectType.DeployUnit,
                "TurnEnd" => ActionEffectType.TurnEnd,
                null or "" => ActionEffectType.Unknown,
                _ => ActionEffectType.CardEffect
            };
        }

        private static void ParseTarget(string raw, ParsedAction action)
        {
            if (string.IsNullOrEmpty(raw))
            {
                action.TargetType = ParsedTargetType.None;
                return;
            }

            var parts = raw.Split('/');

            // 위치형: "x/y"
            if (parts.Length == 2 &&
                int.TryParse(parts[0], out int x) &&
                int.TryParse(parts[1], out int y))
            {
                action.TargetType = ParsedTargetType.Position;
                action.PositionTarget = new Vector2Int(x, y);
                return;
            }

            // 엔티티형: "uid" or "uid1/uid2"
            action.TargetType = ParsedTargetType.EntityList;
            action.EntityTargets.AddRange(parts);
        }
    }
}