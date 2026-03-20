using UnityEngine;
using events;
using events.server;
using events.client;

namespace core
{
    public class ChessGameManager : MonoBehaviour
    {
        [SerializeField] private GameStateStore gameStateStore;
        [SerializeField] private IEventBus eventBus;
        
        /// <summary>
        /// 서버 이벤트의 의미 처리 및 게임 상태 업데이트
        /// </summary>
        /// <param name="serverEvent">발행된 서버 이벤트</param>
        public void HandleServerEvent(IServerEvents serverEvent)
        {
            // TODO: 구체 이벤트 설계 및 구현 필요

        }
        
        /// <summary>
        /// 클라이언트 이벤트의 의미 처리 및 사용자 입력 이벤트 전달
        /// </summary>
        /// <param name="clientEvent">발행된 클라이언트 이벤트</param>
        public void HandleClientEvent(IClientEvents clientEvent)
        {
            // TODO: 구체 이벤트 설계 및 구현 필요
        }

        /// <summary>
        /// 해석된 서버 이벤트를 바탕으로 UI 이벤트 발행
        /// </summary>
        /// <param name="uiEvent">발행할 UI 이벤트</param>
        private void PublishUIEvent(IBaseEvent uiEvent)
        {
            eventBus.Publish(uiEvent);
        }

        // TODO: 게임 세션 관리 로직 구현 (네트워크 연결 필요)
    }
}

