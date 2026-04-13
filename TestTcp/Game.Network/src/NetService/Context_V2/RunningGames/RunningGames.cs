using System.Net.WebSockets;
using System.Runtime.InteropServices;

namespace Game.Network.Service
{
    public interface IGameReader
    {
        public bool IsSessionActive(SessionId id);
    }

    public interface IGameWriter : IGameReader
    {
        public bool TryCreateSession(SessionId id);
        public bool TryEnterPlayer(SessionId sessionId, SessionPlayerId playerId);
        public bool TryExitPlayer(SessionId sessionId, SessionPlayerId playerId);
    }


    public class RunningGames : IGameWriter
    {
        private Dictionary<SessionId, Session> _activeSession = new();
        private ISessionBuilder _sessionBuilder;
        private ISessionPort _port;

        public bool IsSessionActive(SessionId id)
            => _activeSession.ContainsKey(id);

        public bool TryCreateSession(SessionId id)
        {
            var session = _sessionBuilder.BuildSession(id);

            if (session == null || !_activeSession.TryAdd(id, session)) 
            {
                return false;
            }
            return true;

        }
        public bool TryEnterPlayer(SessionId sessionId, SessionPlayerId playerId)
        {
            if (_activeSession.TryGetValue(sessionId, out var session)
                && session.TryAddPlayer(playerId))
            {
                return true;
            }
            return false;
        }

        public bool TryExitPlayer(SessionId sessionId, SessionPlayerId playerId)
        {
            if (_activeSession.TryGetValue(sessionId, out var session))
                return session.RemovePlayer(playerId);
            else return false;
        }

    }

}