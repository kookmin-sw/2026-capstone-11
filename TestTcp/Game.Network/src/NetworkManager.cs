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
            manager.NetEvent.SetReceiveHandler(NetEventHandlerId.System, defaultHandler);
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

        
        public void Send(int handlerId, int queryNum, string ConnId, byte[] raw)
            => NetStream.Send(handlerId, queryNum, ConnId, raw);
        

        public void BroadCast(int handlerId, int queryNum, byte[] raw)
            => NetStream.BroadCast(handlerId, queryNum, raw);
        

        public void Disconnect(string ConnId)
        { 
            NetEvent.CancelAll(ConnId);
            NetStream.Disconnect(ConnId); 
        }

        public Task<string?> ConnectTo(string ipAddr, int portNum, long expireTimeMs)
        => NetConn.ConnectTo(ipAddr, portNum, _netEventQueue, (int)expireTimeMs);
        
        public bool IsConnValid(string connId)
        => NetConn.IsConnValid(connId);

        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, string ConnId, byte[] query_raw, long expireTimeMs)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(ConnId, expireTimeMs);
            NetStream.Query(handlerId, queryNum, ConnId, query_raw);

            return task;
        }
        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, string ConnId, byte[] query_raw, long expireTimeMs, 
                                                        TaskCompletionSource<QueryTaskResult> tcs)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(ConnId, expireTimeMs, tcs);
            NetStream.Query(handlerId, queryNum, ConnId, query_raw);

            return task;
        }


        public Task<QueryTaskResult> AsyncRequestQuery(int handlerId, string ConnId, byte[] query_raw, long expireTimeMs, 
                                                        Action<byte[]>? responseAction, Action? timeOutAction)
        {
            var (queryNum, task) = NetEvent.RegisterQueryTask(ConnId, expireTimeMs, responseAction, timeOutAction);
            NetStream.Query(handlerId, queryNum, ConnId, query_raw);

            return task;
        }

        /// <summary>
        /// 이 함수는 Connection을 항상 보장하지 않음. 별도 핸들러 관리하는 걸 권장
        /// </summary>
        public bool TryGetConnIdList(int minConnCount, out List<string> connIdList)
            => NetConn.TryGetConnIdList(minConnCount, out connIdList);
            
    
        public void SetReceiveHandler(int id, INetEventHandler handler)
            => NetEvent.SetReceiveHandler(id, handler);

        public void SetControlHandler(INetEventHandler handler) 
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