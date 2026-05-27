

// using Game.Network.Protocol;

// namespace Game.Network
// {
//     public class GameMessageModule : ServiceModule
//     {
//         public override int HandlerId => NetEventHandlerId.Constant.GameMessage;

//         public GameMessageModule(INetAPI net, ServiceContext context) : base(net, context) 
//         {}

//         public void OnQuery(ConnId connId, int queryNum, byte[] raw)
//         {
//             if (!Context.TryGetPeer(connId, out var peer)) return;

//             if (peer.Session.session == null) return;
//             byte[]? answer = peer.Session.session.OnGetQuery?.Invoke(peer.Session.playerId, raw);

//             if (answer == null) return;

//             Net.Send(HandlerId, queryNum, connId, answer);
//         }

//         public void OnReceive(ConnId connId, byte[] raw)
//         {
//             if (!Context.TryGetPeer(connId, out var peer)) return;

//             peer.Session.session?.OnGetMessage?.Invoke(peer.Session.playerId, raw);
//         }

//         public void OnRespond(ConnId connId, int queryNum, byte[] raw)
//         {
//             if (!Context.TryGetPeer(connId, out var peer)) return;

//             peer.Session.session?.OnGetResponse?.Invoke(peer.Session.playerId, raw);
//         }
//     }
// }
