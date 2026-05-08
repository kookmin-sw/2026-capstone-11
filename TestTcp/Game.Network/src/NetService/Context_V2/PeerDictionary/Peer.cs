using System.Data;
using System.Net.WebSockets;
using Game.Network.Protocol;

namespace Game.Network.Service
{

    public interface IPeerReader
    {
        public ConnId connId { get; }
        public Peer.State state {get;}
        public int Timer {get;}

        public IConnInfoReader connInfo { get; }
        public ISessionInfoReader sessionInfo { get; }
    }

    public interface IPeerWriter : IPeerReader
    {
        public void SetState(Peer.State state);
        public void ResetTimer();
        public void AddTimer(int delta);
        public IConnInfoWriter connWriter { get; }
        public ISessionInfoWriter sessionWriter { get; }
    }

    public class Peer : IPeerWriter
    {
        public enum State
        {
            Connected,
            Suspended,
            Finished,
        }

        private ConnId _connId;
        private State _state;
        private int _timer;

        private ConnInfo _info;
        private SessionInfo _session;

        public State state => _state;
        public IConnInfoReader connInfo => _info;
        public ISessionInfoReader sessionInfo => _session;

        public IConnInfoWriter connWriter => _info;
        public ISessionInfoWriter sessionWriter => _session;

        // Reader
        public ConnId connId => _connId;
        public int Timer => _timer;

        public Peer(ConnId connId, ConnInfo info)
        {
            _connId = connId;
            _info = info;
            _session = new();
            _timer = 0;
        }

        public void SetState(State state)
        {
            _state = state;
        }

        public void ResetTimer() {_timer = 0;}

        public void AddTimer(int delta) {_timer += delta;}
    }
}