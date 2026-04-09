using System.Diagnostics;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;

namespace Game.Network
{
    public class NetworkManager : INetAPI
    {

        private readonly NetStreamManager NetStream; // OutEvent 생산자
        private readonly NetEventManger NetEvent; // InEvent 소비자
        private readonly NetConnectionManager NetConn; // OutEvent 소비자, -> Connnect InEvemt 셍신지 
        private readonly NetEventQueue _netEventQueue; 

        public static NetworkManager CreateNetworkManager(int portNum, int maxProcessPerTick)
        {
            var manager = new NetworkManager(portNum, maxProcessPerTick);
            var defaultHandler = new SystemHandler(manager);

            manager.NetEvent.SetControlHandler(defaultHandler);
            manager.NetEvent.SetReceiveHandler(defaultHandler);
            return manager;
        }

        public void Start()
        {
            NetStream.Init(_netEventQueue);
            NetEvent.Init(_netEventQueue);
            NetConn.Init(_netEventQueue);
        }

        public void Tick()
        {
            NetStream.Tick(_netEventQueue); 
            NetEvent.Tick(_netEventQueue); 
            NetConn.Tick(_netEventQueue);  
        }

        public string GetNetState()
        {
            return String.Concat(
                NetStream.GetState(),
                NetEvent.GetState(),
                NetConn.GetState()
            );
        }

        
        public void Send(int handlerId, int queryNum, ConnId id, byte[] raw)
            => NetStream.Send(handlerId, queryNum, id, raw);
        

        public void BroadCast(int handlerId, int queryNum, byte[] raw)
            => NetStream.BroadCast(handlerId, queryNum, raw);
        

        public void Disconnect(ConnId id)
        { 
            NetEvent.CancelAll(id);
            NetStream.Disconnect(id); 
        }

        public Task<ConnId?> ConnectTo(string ipAddr, int portNum, long expireTimeMs)
        => NetConn.ConnectTo(ipAddr, portNum, _netEventQueue, (int)expireTimeMs);

        public bool IsConnValid(ConnId id)
        => NetConn.IsConnValid(id);

        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(id, expireTimeMs);
            NetStream.Query(handlerId, queryNum, id, query_raw);

            return task;
        }
        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, 
                                                        TaskCompletionSource<QueryTaskResult> tcs)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(id, expireTimeMs, tcs);
            NetStream.Query(handlerId, queryNum, id, query_raw);

            return task;
        }


        // public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, 
        //                                                 Action<ConnId, byte[]>? responseAction, Action<ConnId>? timeOutAction)
        // {
        //     var (queryNum, task) = NetEvent.RegisterQueryTask(id, expireTimeMs, responseAction, timeOutAction);
        //     NetStream.Query(handlerId, queryNum, id, query_raw);

        //     return task;
        // }

        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, ConnId id, byte[] query_raw, long expireTimeMs, 
                                                        Action<ConnId, QueryTaskResult>? callBack)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(id, expireTimeMs, callBack);
            NetStream.Query(handlerId, queryNum, id, query_raw);

            return task;
        }

        /// <summary>
        /// 이 함수는 Connection을 항상 보장하지 않음. 별도 핸들러 관리하는 걸 권장
        /// </summary>
        public bool TryGetConnIdList(int minConnCount, out List<ConnId> connIdList)
            => NetConn.TryGetConnIdList(minConnCount, out connIdList);
            

        public void SetReceiveHandler(int id, INetEventHandler handler)
            => SetReceiveHandler(handler);

        public void SetReceiveHandler(INetReceiveEventHandler handler)
            => NetEvent.SetReceiveHandler(handler);

        public void SetControlHandler(INetEventHandler handler) 
            => NetEvent.SetControlHandler(handler);

        public void SetControlHandler(INetControlEventHandler handler) 
            => NetEvent.SetControlHandler(handler);

        public async Task StopAsync()
        {
            NetStream.Stop();
            NetEvent.Stop();
            await NetConn.Stop();
        }

        private NetworkManager(int portNum, int maxProcessPerTick)
        {
            
            NetStream = new NetStreamManager(maxProcessPerTick, maxProcessPerTick);
            NetEvent  = new NetEventManger(maxProcessPerTick, maxProcessPerTick);
            NetConn   = new NetConnectionManager(portNum, maxProcessPerTick, maxProcessPerTick);
            
            _netEventQueue = NetEventQueue.CreateNetworkEventQueue();
        }
    }

}