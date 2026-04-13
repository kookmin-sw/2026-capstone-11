using UnityEngine;
using entity.targetable;
using ui.view.unit;

/// <summary>
/// 사용자의 입력과 관련된 클라이언트측 이벤트 타입을 정의
/// </summary>
namespace events.client
{
    public interface IClientEvents
    {
        public class UnitSelectedEvent : IBaseEvent
        {
            public UnitSelectedEvent(UnitView unit)
            {
                Unit = unit;
            }

            public UnitView Unit { get; set; }
            public string UnitUUID => Unit.Id.UUID;
        }

        public class CellSelectedEvent : IBaseEvent
        {
            public CellSelectedEvent(Vector2Int pos)
            {
                Pos = pos;
            }
            
            public Vector2Int Pos { get; set; }
        }

        public class EmptySelectedEvent : IBaseEvent
        {
            // 빈 공간이 선택된 경우 (예: 보드의 빈 칸 클릭)    
        }

        public class HoverEnterEvent : IBaseEvent
        {
            public IHoverable Target;
        }

        public class HoverExitEvent : IBaseEvent
        {
            public IHoverable Target;
        }
    }
}