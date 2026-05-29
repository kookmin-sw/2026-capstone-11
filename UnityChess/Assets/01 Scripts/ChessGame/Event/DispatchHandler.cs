using System;
using UnityEngine;
using Animations;
using evets.Animation;
using static evets.Animation.IAnimationEvents;

namespace events.Animation
{
    public interface IAnimationDispatchHandler
    {
        RenderCommandType type { get; }
        void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus);
    }

    public class MoveDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Move;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitMoveEvent(command));
        }
    }

    public class SpawnDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Deploy;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitDeployEvent(command));
        }
    }

    public class DestroyDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Withdraw;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitDestroyEvent(command));
        }
    }

    public class AttackDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Attack;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitAttackEvent(command));
        }
    }

    public class DamageDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Damage;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitDamageEvent(command));
        }
    }

    public class HealDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Heal;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitHealEvent(command));
        }
    }

    public class SwapDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Swap;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitHealEvent(command));
        }
    }
    public class ApplyBuffDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.BuffApply;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitHealEvent(command));
        }
    }
    public class RemoveBuffDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.BuffRemove;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new UnitHealEvent(command));
        }
    }

    public class DrawCardDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.DrawCard;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new CardDrawEvent(command));
        }
    }

    public class UseCardDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.UseCard;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            eventBus.Publish(new CardUseEvent(command));
        }
    }

    public class EventDispatch : IAnimationDispatchHandler
    {
        public RenderCommandType type => RenderCommandType.Event;

        public void Dispatch(RuntimeRenderCommand command, AnimationEventBus eventBus)
        {
            if (command.extra == "Rule")
            {
                switch (command.timing)
                {
                    case "TurnStart":
                        eventBus.Publish(new TurnStartEvent(command));
                        return;
                    case "TurnEnd":
                        eventBus.Publish(new TurnEndEvent(command));
                        return;
                }
            }
            else
                eventBus.Publish(new EventTriggerEvent(command));
        }
    }
}