

using System;
using System.Threading.Tasks;

namespace Game.Network.Service
{
    public class PingModule_V2 : IServiceModule
    {
        private INetAPI _net;
        private IPeerDictWriter _other;

        private int _pingInterval;
        private int _pingTimeOut;

        private int _lastPingTime;
        
        public void Init(ServiceContext_V2 context)
        {
            _net = context.Net;
            _other = context.Other;

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
            foreach (var peer in _other.PeerReaderList())
                _ = QuaryPing(peer.connId, startTime);

        }

        private Task QuaryPing(ConnId connId, long startTime)
            => _net.AsyncRequestQuery(NetEventHandlerId.Constant.PingPong, connId, Array.Empty<byte>(), _pingTimeOut,
                (answerConnId, answerResult) => PingCallBack(answerConnId, answerResult, startTime)
            );
        
        private void PingCallBack(ConnId connId, QueryTaskResult result, long startTime)
        {
            if (result.IsCancelled || !_other.TryWritePeer(connId, out var peer)) return;
            
            if (result.IsResponded)
            {
                peer.ResetTimer();
                Log.WriteLog($"[Ping] : Got Ping From {connId} | Result : {GameTime.GetNow() - startTime}");
            }
        }
    }

}