using System;
using UnityEngine;
using Core.StateManagement;

namespace Animations
{
    public enum RenderCommandType
    {
        None,
        CardEffect,
        Move,
        Attack,
        Damage,
        Heal,
        Deploy,
        Withdraw,
        Swap,
        BuffApply,
        BuffRemove,
        Event,
        DrawCard,
        UseCard,
    }

    /// <summary>
    /// 실제 렌더링 실행 명령
    /// </summary>
    public class RuntimeRenderCommand
    {
        public RenderCommandType type;

        // entity 대상
        public EntityID source;
        public EntityID target;

        // player 대상
        public string playerId;

        // 위치 정보
        public Vector2Int position;

        // 데미지 / 회복량 등
        public int value;

        // Event ID / Buff ID / Effect ID
        public string extra;

        public string timing;

        // 연출 길이
        public float duration;
    }
}