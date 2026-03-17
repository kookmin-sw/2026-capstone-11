

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
        private int _interval;
        private int _last;

        public PingPongHandler(INetAPI Net, ServiceContext context, int interval)
        {
            _net = Net;
            _context = context;

            _interval = interval;
            _last = 0;

            Net.SetReceiveHandler(Id, this);
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
            => _net.Send(Id, queryNum, ConnId, Array.Empty<byte>());


        public void Tick(int delta)
        {
            _last += delta;
            if (_last < _interval) return;
            _last = 0;

            foreach (var registery in _context.infoPage)
            {
                var connId = registery.Key;
                var info = registery.Value;
                info.pingInfo.lastPingTime = GameTime.GetNow();
                
                _ = _net.AsyncRequestQuery(Id, connId, Array.Empty<byte>(), _interval,
                    (answerRaw) =>
                    {
                        if (!_context.infoPage.TryGetValue(connId, out var targetInfo)) return;

                        targetInfo.pingInfo.currentPingResult = GameTime.GetNow() - targetInfo.pingInfo.lastPingTime;
                    },
                    () => 
                    {
                        if (!_context.infoPage.TryGetValue(connId, out var targetInfo)) return;

                        targetInfo.pingInfo.failureCount--;
                        if (targetInfo.pingInfo.failureCount <= 0) _net.Disconnect(connId);
                    }
                    );
            }
        }        
    }
}