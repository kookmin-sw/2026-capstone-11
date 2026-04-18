namespace Game.Network.Service
{
    public class GameMessageModule : IServiceModule, INetEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.GameMessage;

        private IRouteReader _router;
        private IPeerDictReader _other;
        private IGameWriter _games;

        public void Init(ServiceContext_V2 context)
        {
            _router = context.Router;
            _other = context.Other;
            _games = context.Games;

        
            context.Net.SetReceiveHandler(this);
        }

        public void OnReceive(ConnId connId, byte[] raw)
        {
            if (_other.TryReadPeer(connId, out var peer) 
                && _games.TryGetSession(peer.sessionInfo.id, out var session))
            {
                session.OnGetMessage?.Invoke(peer.sessionInfo.playerId, raw);
            }
        }
        public void OnRespond(ConnId connId, int queryNum, byte[] raw)
        {
            if (_other.TryReadPeer(connId, out var peer) 
                && _games.TryGetSession(peer.sessionInfo.id, out var session))
            {
                session.OnGetResponse?.Invoke(peer.sessionInfo.playerId, raw);
            }
        }
        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            if (_other.TryReadPeer(connId, out var peer) 
                && _games.TryGetSession(peer.sessionInfo.id, out var session))
            {
                session.OnGetQuery?.Invoke(peer.sessionInfo.playerId, raw);
            }
        }



    }   
}