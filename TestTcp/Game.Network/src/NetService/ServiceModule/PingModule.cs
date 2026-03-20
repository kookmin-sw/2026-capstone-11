
using System.Dynamic;

namespace Game.Network
{
    public class PingModule : ServiceModule, INetEventHandler
    {
        public const int Id = 22;
        public override int HandlerId => Id;

        private int _last;

        public PingModule(INetAPI net, ServiceContext context) : base(net, context)
        {
            _last = 0;
        }

        public void Tick(int delta)
        {
            _last += delta;
            if (_last < Context.Opt.pingIntervalMs) return;
            _last = 0;

            foreach (var connId in Context.PeerDictionary.Keys)
            {
                _ = AsyncQueryPing(connId);
            }
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
            => Net.Send(Id, queryNum, ConnId, Array.Empty<byte>());

        private Task AsyncQueryPing(string connId)
        {
            long sentAt = GameTime.GetNow();

            return Net.AsyncRequestQuery(Id, connId, Array.Empty<byte>(), Context.Opt.pingTimeOutMs,
                    (answerRaw) =>
                    {
                        if (!Context.TryGetPeer(connId, out var Peer)) return;

                        Peer.Ping.currentPingResult = GameTime.GetNow() - sentAt;
                        Peer.Ping.failureCount = Context.Opt.pingFailCountToDisconnect;
                    },
                    () =>
                    {
                        if (!Context.TryGetPeer(connId, out var Peer)) return;

                        Peer.Ping.failureCount--;
                        if (Peer.Ping.failureCount <= 0) Net.Disconnect(connId);
                    }
                    );
        }
    }
}