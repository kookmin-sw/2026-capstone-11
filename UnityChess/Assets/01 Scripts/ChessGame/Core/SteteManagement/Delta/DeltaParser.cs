using UnityEngine;
using Core.DTO;
using Core.StateManagement;
using System.Collections.Generic;

namespace Core.Delta
{
    /// <summary>
    /// DTO를 해석한 런타임 Delta
    /// </summary>
    public static class DeltaParser
    {
        public static List<RuntimeDelta> Parse(List<List<string>> dtos, ActionDTO actionContext)
        {
            var result = new List<RuntimeDelta>();
            
            if (dtos == null)
                return result;
            
            foreach (var dto in dtos)
            {
                var delta = ParsePayload(dto, actionContext);

                Debug.Log($"Parsed delta: {delta.Type}");
                result.Add(delta);
            }

            return result;
        }

        private static DeltaType ParseType(string id) => id switch
        {
            "OnEvent" => DeltaType.OnEvent,
            "DamageUnit" => DeltaType.DamageUnit,
            //"HealUnit" => DeltaType.HealUnit,
            "AttackUnit" => DeltaType.AttackUnit,
            "MoveUnit" => DeltaType.MoveUnit,
            "DeployUnit" => DeltaType.DeployUnit,
            "WithdrawUnit" => DeltaType.WithdrawUnit,
            //"ApplyBuff" => DeltaType.ApplyBuff,
            //"RemoveBuff" => DeltaType.RemoveBuff,
            "DrawCard" => DeltaType.DrawCard,
            //"ShuffleDeck" => DeltaType.ShuffleDeck,
            _ => DeltaType.Unknown
        };

        private static RuntimeDelta ParsePayload(List<string> dto, ActionDTO actionContext)
        {
            switch (ParseType(dto[0].Trim()))
            {
                //
                // Event Trigger
                //
                case DeltaType.OnEvent:
                {
                    // P1 = 이벤트 발동 유닛
                    // P2 = Event ID
                    // P3 = 이벤트 발동 시점

                    var delta = new OnEventDelta
                    {
                        Type = DeltaType.OnEvent,
                        actionContext = actionContext,
                        Source = new EntityID(dto[1]),
                        EventId = dto[2],
                        Timing = dto[3]                        
                    };

                    return delta;
                }
                case DeltaType.MoveUnit:
                {
                    // P1 = 유닛 ID
                    // P2 = 이동할 위치 (e.g. "2/3")

                    var delta = new MoveUnitDelta
                    {
                        Type = DeltaType.MoveUnit,
                        actionContext = actionContext,
                        UnitId = new EntityID(dto[1]),
                        Position = ParsePosition(dto[2])
                    };

                    return delta;
                }
                case DeltaType.DeployUnit:
                {
                    // P1 = 유닛 ID
                    // P2 = 배치할 위치 (e.g. "2/3")
                    var delta = new DeployUnitDelta
                    {
                        Type = DeltaType.DeployUnit,
                        actionContext = actionContext,
                        UnitId = new EntityID(dto[1]),
                        Position = ParsePosition(dto[2])
                    };

                    return delta;
                }
                case DeltaType.WithdrawUnit:
                {
                    // P1 = 유닛 ID
                    var delta = new WithdrawUnitDelta
                    {
                        Type = DeltaType.WithdrawUnit,
                        actionContext = actionContext,
                        UnitId = new EntityID(dto[1])
                    };

                    return delta;
                }
                case DeltaType.AttackUnit:
                {
                    // P1 = 공격 대상 유닛 ID
                    // P2 = 공격 유닛 ID
                    var delta = new AttackUnitDelta
                    {
                        Type = DeltaType.AttackUnit,
                        actionContext = actionContext,
                        UnitId = new EntityID(dto[2]),
                        TargetId = new EntityID(dto[1])
                    };
                    
                    return delta;
                }
                case DeltaType.DamageUnit:
                {
                    // P1 = 유닛 ID
                    // P2 = 피해량
                    var delta = new DamageUnitDelta
                    {
                        Type = DeltaType.DamageUnit,
                        actionContext = actionContext,
                        UnitId = new EntityID(dto[1]),
                        Damage = int.Parse(dto[2])
                    };

                    return delta;
                }
                case DeltaType.DrawCard:
                {
                    // P1 = 플레이어 ID
                    // P2 = 드로우할 카드 수
                    var delta = new DrawCardDelta
                    {
                        Type = DeltaType.DrawCard,
                        actionContext = actionContext,
                        PlayerId = dto[1],
                        Count = int.Parse(dto[2])
                    }; 

                    return delta;
                }
                default:
                    Debug.LogWarning($"알 수 없는 Delta ID: {dto[0]}");
                    return new UnknownDelta { Type = DeltaType.Unknown, actionContext = actionContext };
            }
        }

        private static Vector2Int ParsePosition(string pos)
        {
            var parts = pos.Split('/');
            return new Vector2Int(int.Parse(parts[0]), int.Parse(parts[1]));
        }
    }
}