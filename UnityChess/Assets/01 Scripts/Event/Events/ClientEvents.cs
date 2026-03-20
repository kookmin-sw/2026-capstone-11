using UnityEngine;
using entity.targetable;

/// <summary>
/// 사용자의 입력과 관련된 클라이언트측 이벤트 타입을 정의
/// </summary>
namespace events.client
{
    public interface IClientEvents
    {
        public class UnitSelectedEvent : IBaseEvent
        {
            public string UnitUUID { get; set; }
        }

        public class CellSelectedEvent : IBaseEvent
        {
            public Vector2Int Pos { get; set; }
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