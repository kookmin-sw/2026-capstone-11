using UnityEngine;
using Core.StateManagement;
using Core.DTO;
using System;

namespace Core.Delta
{
    public enum DeltaType
    {
        MoveUnit,
        DeployUnit,
        WithdrawUnit,
        AttackUnit,
        DamageUnit,

        DrawCard,
        UseCard,

        OnEvent,

        Unknown
    }

    public class RuntimeDelta
    {
        public DeltaType Type { get; set; }
        public ActionDTO actionContext;
    }

    public class MoveUnitDelta : RuntimeDelta
    {
        public EntityID UnitId;
        public Vector2Int Position;

        public MoveUnitDelta()
        {
            
        }
    }

    public class DeployUnitDelta : RuntimeDelta
    {
        public EntityID UnitId;
        public Vector2Int Position;

        public DeployUnitDelta()
        {
            Type = DeltaType.DeployUnit;
        }
    }

    public class WithdrawUnitDelta : RuntimeDelta
    {
        public EntityID UnitId;

        public WithdrawUnitDelta()
        {
            Type = DeltaType.WithdrawUnit;
        }
    }

    public class AttackUnitDelta : RuntimeDelta
    {
        public EntityID UnitId;
        public EntityID TargetId;

        public AttackUnitDelta()
        {
            Type = DeltaType.AttackUnit;
        }
    }

    public class DamageUnitDelta : RuntimeDelta
    {
        public EntityID UnitId;
        public int Damage;

        public DamageUnitDelta()
        {
            Type = DeltaType.DamageUnit;
        }
    }
    
    public class DrawCardDelta : RuntimeDelta
    {
        public string PlayerId;
        public int Count;

        public DrawCardDelta()
        {
            Type = DeltaType.DrawCard;
        }
    }

    public class OnEventDelta : RuntimeDelta
    {
        public EntityID Source;
        public string EventId;
        public string Timing;

        public OnEventDelta()
        {
            Type = DeltaType.OnEvent;
        }
    }

    public class UnknownDelta : RuntimeDelta
    {
        public string RawType;

        public UnknownDelta()
        {
            Type = DeltaType.Unknown;
        }
    }
}