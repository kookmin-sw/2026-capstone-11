

using System.Collections.ObjectModel;
using System.Net.WebSockets;

namespace Game.Network
{
    public class Session
    {
        private ISessionPort _port;
        private SessionId _id;
        private int _minPlayer;
        private int _maxPlayer;
        private bool _isSessionStarted;
        private bool _isSessionEnded;
        private bool _isSessionRunnable;
        private List<SessionPlayerId> _playersInSession;
        public Session(ISessionPort port, SessionId id, int minPlayer, int maxPlayer)
        {
            if (minPlayer <= 0 || maxPlayer <= 0 || maxPlayer < minPlayer) throw new ArgumentException();
            _port = port;
            _id = id; 
            _minPlayer = minPlayer;
            _maxPlayer = maxPlayer;
            _isSessionStarted = false;
            _isSessionEnded = false;
            _isSessionRunnable = false;
            _playersInSession = new(maxPlayer);
        }

        public ISessionPort Port => _port;
        public SessionId SessionId => _id; 
        public IReadOnlyList<SessionPlayerId> Members => _playersInSession.AsReadOnly();

        public Action? OnSessionStart {get; set;}
        public Action? OnSessionEnd {get; set;}

        public Action<SessionPlayerId>? OnPlayerEnter {get; set;}

        /// <summary>
        /// Don't Call Send or Query to Exit Player
        /// </summary>
        public Action<SessionPlayerId>? OnPlayerExit {get; set;}

        public Func<SessionPlayerId, byte[], byte[]>? OnGetQuery { get; set; }
        public Action<SessionPlayerId, byte[]>? OnGetResponse { get; set; }
        public Action<SessionPlayerId, byte[]>? OnGetMessage { get; set; }


        public bool IsSessionMemberReady => Members.Count() >= _minPlayer;

        public void SendPlayer(SessionPlayerId receiver, byte[] raw) 
            => _port.SendPlayer(_id, receiver, raw);

        public void QueryPlayer(SessionPlayerId receiver, byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction)        
            => _port.QueryPlayer(_id, receiver, raw, timeOutMs, succAction, timeOutAction);

        public void SendHost(byte[] raw) 
            => _port.SendHost(_id, raw);

        public void QueryHost(byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction)
            => _port.QueryHost(_id, raw, timeOutMs, succAction, timeOutAction);
        


        public bool TryAddPlayer(SessionPlayerId id)
        {
            if (Members.Count >= _maxPlayer) 
            { 
                id = SessionPlayerId.Default;
                return false;
            }
            _playersInSession.Add(id);
            return true;
        } 

        public bool RemovePlayer(SessionPlayerId id)
            => _playersInSession.Remove(id);
    }
}