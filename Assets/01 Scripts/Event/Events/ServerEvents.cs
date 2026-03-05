using UnityEngine;

/// <summary>
/// 서버에서 수신하는 패킷과 관련된 서버측 이벤트 타입을 정의
/// </summary>
namespace events.server
{
    public interface IServerEvents
    {
        // 유닛 관련 이벤트
        /// <summary>
        /// 유닛 소환 이벤트
        /// </summary>
        public class UnitSpawnEvent : BaseEvent
        {
            string unitID;
        }

        /// <summary>
        /// 유닛 이동 이벤트
        /// </summary>
        public class UnitMoveEvent : BaseEvent
        {
            string unitID;
            Vector2Int from;
            Vector2Int to;
        }

        /// <summary>
        /// 유닛 파괴 이벤트
        /// </summary>
        public class UnitDestroyed : BaseEvent
        {
            string unitID;
        }

        /// <summary>
        /// 유닛 피격 이벤트
        /// </summary>
        public class UnitDamaged : BaseEvent
        {
            string unitID;
        }

        // 카드 관련 이벤트
        /// <summary>
        /// 카드 드로우 이벤트
        /// </summary>
        public class CardAddedToHand : BaseEvent
        {
            string unitID;
        }

        /// <summary>
        /// 카드 제거 이벤트
        /// </summary>
        public class CardRemovedFromHand : BaseEvent
        {
            
        }

        /// <summary>
        /// 카드 영역 이동 이벤트
        /// </summary>
        public class CardMoveEvent : BaseEvent
        {
            
        }

        /// <summary>
        /// 카드 사용시 이벤트
        /// </summary>
        public class CardPlayedEvent : BaseEvent
        {
            
        }
    }
}