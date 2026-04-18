using System.IO.Compression;
using System.Net.WebSockets;

namespace Game.Network.Service
{
    public interface IRouteReader
    {
        bool TryRouting(SessionId sessionId, SessionPlayerId playerId, out ConnId id);
        public int RouteCount {get;}
    }

    public interface IRouteWriter : IRouteReader
    {
        void AddRoute(SessionId sessionId, SessionPlayerId playerId, ConnId connId);
        bool RemoveRoute(SessionId sessionId, SessionPlayerId playerId, out ConnId id);
    }

    public class RoutingMap : IRouteWriter
    {
        private Dictionary<(SessionId, SessionPlayerId), ConnId> _sessionToConnMap = new();

        public int RouteCount => _sessionToConnMap.Count;

        public bool TryRouting(SessionId sessionId, SessionPlayerId playerId, out ConnId id)
            => _sessionToConnMap.TryGetValue((sessionId, playerId), out id);

        public void AddRoute(SessionId sessionId, SessionPlayerId playerId, ConnId connId)
            => _sessionToConnMap.Add((sessionId, playerId), connId);

        public bool RemoveRoute(SessionId sessionId, SessionPlayerId playerId, out ConnId id)
            => _sessionToConnMap.Remove((sessionId, playerId), out id);

    };
}