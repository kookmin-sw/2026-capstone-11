using UnityEngine;
using events;
using Animations;
using UnityEngine.Rendering.Universal;

/// <summary>
/// 게임 진행 중 재생될 애니메이션 이벤트 타입을 정의
/// </summary>
namespace evets.Animation
{
    public interface IAnimationEvents
    {
        // 유닛 관련 이벤트
        /// <summary>
        /// 유닛 소환 이벤트
        /// </summary>
        public class UnitDeployEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public UnitDeployEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 유닛 이동 이벤트
        /// </summary>
        public class UnitMoveEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public UnitMoveEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 유닛 파괴 이벤트
        /// </summary>
        public class UnitDestroyEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public UnitDestroyEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 유닛 피격 이벤트
        /// </summary>
        public class UnitDamageEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public UnitDamageEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        // 카드 관련 이벤트
        /// <summary>
        /// 카드 드로우 이벤트
        /// </summary>
        public class CardDrawEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public CardDrawEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 카드 제거 이벤트
        /// </summary>
        public class CardUseEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public CardUseEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 게임 시스템 이벤트
        /// </summary>
        public class TurnStartEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public TurnStartEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        public class TurnEndEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public TurnEndEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }

        /// <summary>
        /// 유닛 이벤트
        /// </summary>
        public class EventTriggerEvent : IBaseEvent
        {
            public RuntimeRenderCommand cmd;

            public RenderCommandType Type => cmd.type;

            public EventTriggerEvent(RuntimeRenderCommand command)
            {
                cmd = command;
            }
        }
    }
}