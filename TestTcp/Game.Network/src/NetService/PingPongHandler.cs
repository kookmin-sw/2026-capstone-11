

using System.Net.Sockets;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;

namespace Game.Network
{
    public class PingPongHandler : INetEventHandler
    {

        public const int Id = 22;
        private INetAPI _net;
        private ServiceContext _context;
        private int _last;

        public PingPongHandler(INetAPI Net, ServiceContext context)
        {
            _net = Net;
            _context = context;
            _last = 0;
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
            => _net.Send(Id, queryNum, ConnId, Array.Empty<byte>());


        public void Tick(int delta)
        {
            _last += delta;
            if (_last < _context.Opt.pingIntervalMs) return;
            _last = 0;

            foreach (var registery in _context.InfoDictionary)
            {
                var connId = registery.Key;
                var ping = registery.Value.Ping;
                ping.lastPingTime = GameTime.GetNow();
                
                _ = _net.AsyncRequestQuery(Id, connId, Array.Empty<byte>(), _context.Opt.pingTimeOutMs,
                    (answerRaw) =>
                    {
                        if (!_context.TryGetInfo(connId, out var targetInfo)) return;

                        targetInfo.Ping.currentPingResult = GameTime.GetNow() - targetInfo.Ping.lastPingTime;
                        targetInfo.Ping.failureCount = _context.Opt.pingFailCountToDisconnect;
                    },
                    () => 
                    {
                        if (!_context.TryGetInfo(connId, out var targetInfo)) return;

                        targetInfo.Ping.failureCount--;
                        if (targetInfo.Ping.failureCount <= 0) _net.Disconnect(connId);
                    }
                    );

            }
        }    

    }
}