

using System.Net.Sockets;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;

namespace Game.Network
{
    public class PingPong
    {
        public long _lastPing;
        public long _interval;
        public Task<QueryTaskResult>? _pingTask;

        public PingPong() { _lastPing = 0; _interval = 0; _pingTask = null; }
    }


    public class PingPongHandler : INetEventHandler
    {
        private INetAPI _net;
        private int _interval;
        private int _last;

        private const int _thres = 10;
        private Dictionary<string, PingPong> _pingPongDict;


        public PingPongHandler(INetAPI Net, int interval)
        {
            _net = Net;
            _interval = interval;
            _last = 0;
            _pingPongDict = new();
        }

        public void Tick(int delta)
        {
            _last += delta;
            if (_last < _interval) return;
            _last = 0;

            long now = GameTime.GetNow();
            foreach (var item in _pingPongDict)
            {
                var id = item.Key;
                var pp = item.Value;

                if (pp._pingTask != null && pp._pingTask.IsCompleted)
                {
                    var result = pp._pingTask.Result;
                    if (result.IsResponded)
                    {
                        var interval = BitConverter.ToInt64(result.AnswerRaw) - pp._lastPing;
                        Log.WriteLog($"[PingPong] Complete. Interval : {interval}");
                    }
                    else
                        Log.WriteLog($"[PingPong] Failed");
                    
                    pp._pingTask = null;
                }

                if (pp._pingTask == null)
                {
                    pp._lastPing = now;
                    byte[] data = BitConverter.GetBytes(pp._lastPing);
                    Log.WriteLog($"[Ping] : {now}");
                    pp._pingTask = _net.AsyncRequestQuery(NetEventHandlerId.PingPong, id, data, 3000);
                }

            }
        }

        public void OnReceive(string ConnId, byte[] raw)
        {
            Log.WriteLog($"[PingPong] OnReceive");
        }

        public void OnRespond(string ConnId, int queryNum, byte[] raw)
        {
            Log.WriteLog($"[GetPong] : {queryNum}.");
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
        {   
            long time = GameTime.GetNow();
            Log.WriteLog($"[GetPing] : {queryNum} | [SendPong] {time}");
            _net.Send(
                NetEventHandlerId.PingPong,
                queryNum,
                ConnId,
                BitConverter.GetBytes(time)
            );

        }

        public void OnDisconnect(string ConnId, byte[] raw) 
            => _pingPongDict.Remove(ConnId);
        public void OnException(string ConnId, byte[] raw, string msg) 
            => _pingPongDict.Remove(ConnId);
        public void OnHello(string ConnId, byte[] raw)
            => _pingPongDict.TryAdd(ConnId, new PingPong());
    }
}