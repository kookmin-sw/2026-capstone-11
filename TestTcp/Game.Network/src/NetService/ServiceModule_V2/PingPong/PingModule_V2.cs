

namespace Game.Network.Service
{
    public class PingModule_V2 : IServiceModule
    {
        private INetAPI _net;
        private IPeerDictPingWriter _toWrite;
        private IPeerDictReader _toRead;

        private int _failureCount;
        private int _pingInterval;
        private int _pingTimeOut;

        private int _lastPingTime;
        
        public void Init(ServiceContext_V2 context)
        {
            _net = context.Net;
            _toWrite = context.Other;
            _toRead = context.Other;

            _failureCount = context.Opt.pingFailCountToDisconnect;
            _pingInterval = context.Opt.pingIntervalMs;
            _pingTimeOut = context.Opt.pingTimeOutMs;

            _lastPingTime = 0;
        } 

        public void Tick(int delta)
        {   
            _lastPingTime += delta;
            if (_lastPingTime < _pingInterval) return;

            _lastPingTime = 0;
            Log.WriteLog("Ping!");


            var startTime = GameTime.GetNow();
            foreach (var peer in _toRead.ReadPeers())
                _ = QuaryPing(peer.connId, startTime);

        }

        private Task QuaryPing(ConnId connId, long startTime)
            => _net.AsyncRequestQuery(NetEventHandlerId.Constant.PingPong, connId, Array.Empty<byte>(), _pingTimeOut,
                (answerConnId, answerResult) => PingCallBack(answerConnId, answerResult, startTime)
            );
        
        private void PingCallBack(ConnId connId, QueryTaskResult result, long startTime)
        {
            if (result.IsCancelled || !_toWrite.TryGetPing(connId, out var pingInfo)) return;
            
            if (result.IsResponded)
            {
                var end = GameTime.GetNow();
                pingInfo.currentPingResult = end - startTime;
                pingInfo.failureCount = _failureCount;

                Log.WriteLog($"[Ping] : Got Ping From {connId} | Result : {pingInfo.currentPingResult}");
            }
            else // result.IsTimeOut 
            {
                pingInfo.failureCount--;

                Log.WriteLog($"[Ping] : Fail Ping From {connId} | Remain Fail Count : {pingInfo.failureCount}");
            }
        }
    }

}