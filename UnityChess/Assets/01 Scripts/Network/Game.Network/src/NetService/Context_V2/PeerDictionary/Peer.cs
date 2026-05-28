using System.Net.WebSockets;
using Game.Network.Protocol;

namespace Game.Network.Service
{

    public interface IPeerReader
    {
        public ConnId connId { get; }
        public IConnInfoReader connInfo { get; }
        public ISessionInfoReader sessionInfo { get; }
        public long Latency { get; }
    }

    public interface IPeerWriter : IPeerReader
    {
        public IConnInfoWriter connWriter { get; }
        public ISessionInfoWriter sessionWriter { get; }
        public PingInfo ping { get; }

    }

    public class Peer : IPeerWriter
    {
        private ConnId _connId;
        private ConnInfo _info;
        private SessionInfo _session;
        private PingInfo _ping;

        public PingInfo ping => _ping;
        public IConnInfoReader connInfo => _info;
        public ISessionInfoReader sessionInfo => _session;

        public IConnInfoWriter connWriter => _info;
        public ISessionInfoWriter sessionWriter => _session;

        // Reader
        public ConnId connId => _connId;
        public long Latency => _ping.currentPingResult;

        public Peer(ConnId connId, ConnInfo info)
        {
            _connId = connId;
            _info = info;
            _session = new();
            _ping = new();
        }
    }
}