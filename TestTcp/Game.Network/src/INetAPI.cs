
using System.Collections.Concurrent;

namespace Game.Network
{
    public interface INetAPI
    {
        /// <summary>
        /// 특정 ConnId 연결에 raw를 전송. 
        /// 메세지 처리에 대한 handler는 handlerId가 지정
        /// queryNum == 0일시 일반 전송. != 0인 경우 해당 쿼리번호에 해당하는 클라이언트 쿼리에 응답.
        /// </summary>
        public void Send(int handlerId, int queryNum, ConnId id, byte[] raw);


        /// <summary>
        /// 모든 연결에 raw를 전송. 
        /// 메세지 처리에 대한 handler는 handlerId가 지정
        /// queryNum == 0일시 일반 전송. != 0인 경우 해당 쿼리번호에 해당하는 클라이언트 쿼리에 응답.
        /// </summary>
        public void BroadCast(int handlerId, int queryNum, byte[] raw);

        /// <summary>
        /// 특정 ConnId의 연결을 중단.
        /// Disconnect 처리에 대한 handler는 handerId가 지정
        /// </summary>
        public void Disconnect(ConnId id);

        /// <summary>
        /// 특정 ConnId에 대한 쿼리 등록 후 raw 전송. 
        /// 쿼리는 queryNum이 발급되어 raw와 함께 전송되며, 이는 NetEventHandler의 OnReceive()에 전달. 
        /// 특정 queryNum이 도착할때 또는 expireTimeMs(밀리초)동안 대기하는 Task 반환.
        /// Task는 QueryTaskResult(bool InTime, byte[] AnswerRaw) 을 반환.
        /// expire시 (false, Array.Empty<byte>), 도착시 (true, *대답으로 받은 raw 데이터*)   
        /// </summary>
        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs);

        /// <summary>
        /// 특정 ConnId에 대한 쿼리 등록 후 raw 전송. 
        /// 쿼리는 queryNum이 발급되어 raw와 함께 전송되며, 이는 NetEventHandler의 OnReceive()에 전달. 
        /// 특정 queryNum이 도착할때 또는 expireTimeMs(밀리초)동안 대기하는 Task 반환.
        /// Task는 QueryTaskResult(bool InTime, byte[] AnswerRaw) 을 반환.
        /// expire시 (false, Array.Empty<byte>), 도착시 (true, *대답으로 받은 raw 데이터*)   
        /// </summary>
        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, TaskCompletionSource<QueryTaskResult> tcs);

        /// <summary>
        /// 특정 ConnId에 대한 쿼리 등록 후 raw 전송. 
        /// 쿼리는 queryNum이 발급되어 raw와 함께 전송되며, 이는 NetEventHandler의 OnReceive()에 전달.
        /// 특정 queryNum이 도착할때 또는 expireTimeMs(밀리초)동안 대기하는 Task 반환.
        /// Task는 QueryTaskResult(bool InTime, byte[] AnswerRaw) 을 반환.
        /// expire시 (false, Array.Empty<byte>), 도착시 (true, *대답으로 받은 raw 데이터*).   
        /// responseAction은 쿼리 응답시 호출, timeOutAction은 expire시 호출.
        /// **위 콜백은 기본적은 Exception handling이 없음**
        /// </summary>
        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, Action<ConnId, QueryTaskResult>? callBack);
        
        // public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, Action<ConnId, byte[]>? responseAction, Action<ConnId>? timeOutAction);

        /// <summary>
        /// 현재 연결된 Connection id를 조회.
        /// 연결된 Connection 수가 minConnCount 이하일 경우 false.
        /// 반환된 연결이 항상 Connection을 보장하진 않음.
        /// </summary>
        public bool TryGetConnIdList(int minConnCount, out List<ConnId> connIdList); 

        /// <summary>
        /// handler 등록
        /// 받은 메세지의 handlerId와 일치하는 NetEventHandler의 OnReceive 함수 호출.
        /// </summary>
        public void SetReceiveHandler(int handerId, INetEventHandler handler);

        public void SetReceiveHandler(INetReceiveEventHandler handler);

        /// <summary>
        /// NetInEvent 중 Control에 해당하는 OnDisconnect, OnException, OnHello에 반응하는 handler 등록
        /// </summary>
        public void SetControlHandler(INetEventHandler handler);
        public void SetControlHandler(INetControlEventHandler handler);

        public bool IsConnValid(ConnId id);

        /// <summary>
        /// 해당 IP 주소와 포트 번호로 Connection을 생성.
        /// 성공시 해당 ConnId, 실패시 null 리턴.
        /// </summary>
        /// <param name="ipAddr"></param>
        /// <param name="portNum"></param>
        /// <param name="expireTimeMs"></param>
        /// <returns></returns> 
        public Task<ConnId?> ConnectTo(string ipAddr, int portNum, long expireTimeMs); 
    }

}