using System.Collections.Generic;
using Core.Delta;
using Core.StateManagement;

namespace Animations
{
    public interface IRenderCommnandBuildHandler
    {
        DeltaType type { get; }

        void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result);
    }

    public class MoveCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.MoveUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var moveDelta = delta as MoveUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Move,
                target = moveDelta.UnitId,
                position = moveDelta.Position,
                duration = 0.2f
            };

            result.Add(cmd);
        }
    }

    public class DeployCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.DeployUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var deployDelta = delta as DeployUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Deploy,
                target = deployDelta.UnitId,
                position = deployDelta.Position,
                duration = 0.25f
            };

            result.Add(cmd);
        }
    }

    public class WithdrawCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.WithdrawUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var withdrawDelta = delta as WithdrawUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Withdraw,
                target = withdrawDelta.UnitId,
                duration = 0.75f
            };

            result.Add(cmd);
        }
    }

    public class AttackCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.AttackUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var attackDelta = delta as AttackUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Attack,
                source = attackDelta.UnitId,
                target = attackDelta.TargetId,
                duration = 0.9f
            };

            result.Add(cmd);
        }
    }

    public class DamageCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.DamageUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var damageDelta = delta as DamageUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Damage,
                target = damageDelta.UnitId,
                value = damageDelta.Damage,
                duration = 0.25f
            };

            result.Add(cmd);
        }
    }

    public class HealCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.HealUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var healDelta = delta as HealUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Heal,
                target = healDelta.UnitId,
                value = healDelta.heal,
                duration = 0.7f
            };

            result.Add(cmd);
        }
    }

    public class SwapCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.SwapUnit;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var swapDelta = delta as SwapUnitDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Swap,
                source = swapDelta.Unit1,
                target = swapDelta.Unit2,
                duration = 0.5f
            };

            result.Add(cmd);
        }
    }

    public class ApplyBuffBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.ApplyBuff;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var buffDelta = delta as ApplyBuffDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.BuffApply,
                extra = buffDelta.buffId,
                value = buffDelta.amount,
                duration = 0.05f
            };

            result.Add(cmd);
        }
    }

    public class RemoveBuffBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.RemoveBuff;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var buffDelta = delta as RemoveBuffDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.BuffRemove,
                extra = buffDelta.buffId,
                duration = 0.05f
            };

            result.Add(cmd);
        }
    }

    public class CardDrawCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.DrawCard;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var drawDelta = delta as DrawCardDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.DrawCard,
                playerId = drawDelta.PlayerId,
                value = drawDelta.Count,
                duration = 1f
            };

            result.Add(cmd);
        }
    }

    public class CardUseCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.Unknown;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.UseCard,
                target = action.source.Uid,
                duration = 0.3f
            };

            result.Add(cmd);
        }
    }

    public class EventCommandBuilder : IRenderCommnandBuildHandler
    {
        public DeltaType type => DeltaType.OnEvent;

        public void Build(RuntimeAction action, RuntimeDelta delta, List<RuntimeRenderCommand> result)
        {
            var eventDelta = delta as OnEventDelta;

            var cmd = new RuntimeRenderCommand
            {
                type = RenderCommandType.Event,
                source = eventDelta.Source,
                extra = eventDelta.EventId,
                timing = eventDelta.Timing,
                duration = 0.1f
            };

            result.Add(cmd);
        }
    }
}