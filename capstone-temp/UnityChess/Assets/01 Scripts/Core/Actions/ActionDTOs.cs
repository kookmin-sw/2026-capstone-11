using System.Collections.Generic;
using UnityEngine;

namespace core.actions
{
    public enum ActionEffectType
    {
        CardEffect,
        DefaultMove,
        DeployUnit,
        TurnEnd,
        Unknown
    }

    public enum ParsedTargetType
    {
        None,
        Position,
        EntityList
    }

    /// <summary>
    /// 서버 원본 액션 DTO
    /// </summary>
    public class ActionDTO
    {
        public string UID;
        public string EffectID;
        public string Source;
        public string Target;
    }

    /// <summary>
    /// 파싱된 액션
    /// </summary>
    public class ParsedAction
    {
        public string UID;
        public string EffectID;
        public ActionEffectType EffectType;

        public string Source;
        public string RawTarget;

        public ParsedTargetType TargetType;

        // 위치형 타겟
        public Vector2Int? PositionTarget;

        // 엔티티형 타겟
        public List<string> EntityTargets = new();

        public bool HasNoTarget => TargetType == ParsedTargetType.None;
    }
}