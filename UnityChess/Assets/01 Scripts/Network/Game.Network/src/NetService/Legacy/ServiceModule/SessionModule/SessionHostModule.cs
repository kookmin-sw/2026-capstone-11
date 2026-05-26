
// using Game.Network.Protocol;

// namespace Game.Network
// {
//     public class SessionHostModule : SessionModule
//     {
//         protected Dictionary<(SessionId, SessionPlayerId), ServicePeer> _routingMap = new();
//         public SessionHostModule(INetAPI net, ServiceContext context, ISessionBuilder builder) 
//         : base(net, context, builder) {}


//         public void OnQuery(ConnId connId, int queryNum, byte[] raw)
//         {
//             if (Context.TryGetPeer(connId, out var peer) 
//                 && JoinAndInvokeSession(peer))
//             {
//                 Net.Send(HandlerId, queryNum, connId, AcceptedMSG);
//             }

//             // Fail to Enter Peer
//             Net.Send(HandlerId, queryNum, connId, RejectedMSG);
//         }

//         protected override bool JoinToSession(ServicePeer peer)
//         {    
//             if (!base.JoinToSession(peer))
//             {
//                 _routingMap.Remove((peer.Session.sessionId, peer.Session.playerId));
//                 return false;
//             }
//             _routingMap.Add((peer.Session.sessionId, peer.Session.playerId), peer);
//             return true;
//         }

//         protected override bool ExitToSession(ServicePeer peer)
//         {
//             if (!base.ExitToSession(peer)) return false;

//             return _routingMap.Remove((peer.Session.sessionId, peer.Session.playerId));
//         }

//         public override void SendPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw)
//         {
//             if (!_routingMap.TryGetValue((sessionId, receiver), out var peer)) return;

//             Net.Send(NetEventHandlerId.Constant.GameMessage, 0, peer.ConnectionId, raw);
//         }
//         public override void QueryPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction)
//         {
//             // TODO: Cancel Action
//             if (!_routingMap.TryGetValue((sessionId, receiver), out var peer)) return;

//             _ = Net.AsyncRequestQuery(NetEventHandlerId.Constant.GameMessage, peer.ConnectionId, raw, timeOutMs, succAction, timeOutAction);
//         }

//         public override void SendHost(SessionId sessionId, byte[] raw) {}
//         public override void QueryHost(SessionId sessionId, byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction) {}
//     }
// }