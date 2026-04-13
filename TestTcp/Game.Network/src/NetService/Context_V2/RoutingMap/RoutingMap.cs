using System.IO.Compression;
using System.Net.WebSockets;

namespace Game.Network.Service
{
    public interface IRouteReader
    {
        bool TryRouting(SessionId sessionId, SessionPlayerId playerId, out ConnId id);
    }

    public interface IRouteWriter : IRouteReader
    {
        void AddRoute(SessionId sessionId, SessionPlayerId playerId, ConnId connId);
        bool RemoveRoute(SessionId sessionId, SessionPlayerId playerId, out ConnId id);
    }

    public class RoutingMap : IRouteWriter
    {
        private Dictionary<(SessionId, SessionPlayerId), ConnId> _routingMap = new();

        public bool TryRouting(SessionId sessionId, SessionPlayerId playerId, out ConnId id)
            => _routingMap.TryGetValue((sessionId, playerId), out id);
        

        public void AddRoute(SessionId sessionId, SessionPlayerId playerId, ConnId connId)
            => _routingMap.Add((sessionId, playerId), connId);

        public bool RemoveRoute(SessionId sessionId, SessionPlayerId playerId, out ConnId id)
            => _routingMap.Remove((sessionId, playerId), out id);

    };
}