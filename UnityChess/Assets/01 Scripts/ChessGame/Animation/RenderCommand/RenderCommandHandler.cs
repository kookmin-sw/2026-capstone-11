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