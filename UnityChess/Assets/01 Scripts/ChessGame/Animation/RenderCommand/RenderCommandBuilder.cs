using System.Collections.Generic;
using Core.Delta;
using Core.StateManagement;
using Game.Network;
using UnityEngine;

namespace Animations
{
    public static class RenderCommandBuilder
    {
        private static Dictionary<DeltaType, IRenderCommnandBuildHandler> handlers = new Dictionary<DeltaType, IRenderCommnandBuildHandler>
        {
            { DeltaType.MoveUnit, new MoveCommandBuilder() },
            { DeltaType.DeployUnit, new DeployCommandBuilder() },
            { DeltaType.WithdrawUnit, new WithdrawCommandBuilder() },
            { DeltaType.DamageUnit, new DamageCommandBuilder() },
            { DeltaType.DrawCard, new CardDrawCommandBuilder() },
            { DeltaType.OnEvent, new EventCommandBuilder() }
        };

        public static List<RuntimeRenderCommand> Build(RuntimeAction action, List<RuntimeDelta> deltas)
        {
            var result = new List<RuntimeRenderCommand>();
            
            // 카드 사용 액션일 경우 카드 사용 명령 추가
            if (action != null && !(action.effectType == RuntimeActionEffectType.TurnEnd 
                || action.effectType == RuntimeActionEffectType.DefaultMove
                || action.effectType == RuntimeActionEffectType.Unknown))
            {
                var handler = new CardUseCommandBuilder();

                handler.Build(action, null, result);
            }

            foreach (var delta in deltas)
            {
                Debug.Log($"Delta Type: {delta.Type}");
                if (handlers.TryGetValue(delta.Type, out var handler))
                {
                    Debug.Log($"Building command for delta type {delta.Type}");
                    handler.Build(action, delta, result);
                }
            }

            return result;
        }
    }
}