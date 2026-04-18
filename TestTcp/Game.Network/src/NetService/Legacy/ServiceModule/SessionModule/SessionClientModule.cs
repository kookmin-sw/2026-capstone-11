
// namespace Game.Network
// {
//     public class SessionClientModule : SessionModule
//     {
//         private ServicePeer? _host = null;
//         public SessionClientModule(INetAPI net, ServiceContext context, ISessionBuilder builder) 
//         : base(net, context, builder) { }


//         public void RequestEnterRemoteSession(ConnId connId, long timeOutMs, Action succAction, Action failAction)
//         {
//             if (!Context.PeerDictionary.ContainsKey(connId)) 
//             { 
//                 failAction.Invoke(); 
//                 Log.WriteLog("No such Service Connected");
//                 return; 
//             }
            
//             _ = Net.AsyncRequestQuery(HandlerId, connId, Array.Empty<byte>(), timeOutMs,
//                 (answerRaw) =>
//                 {
//                     if (IsAcceptMSG(answerRaw) 
//                         && Context.TryGetPeer(connId, out var peer) 
//                         && JoinAndInvokeSession(peer))
//                         { succAction.Invoke(); }

//                     else failAction.Invoke();
//                 },
//                 () => failAction.Invoke()
//             ); 
//         }


//         /// <summary>
//         /// host don't check overwrite.
//         /// </summary>
//         /// <param name="peer"></param>
//         /// <returns></returns>
//         protected override bool JoinToSession(ServicePeer peer)
//         {
//             // OnPlayerEnter 호출 대비, host 우선 업데이트
//             _host = peer;
//             if (!base.JoinToSession(peer))
//             {
//                 _host = null;
//                 return false;
//             }
//             return true;
//         }

//         protected override bool ExitToSession(ServicePeer peer)
//         {
//             bool succ = base.ExitToSession(peer);
//             _host = null;
//             return succ;
//         }


//         public override void SendPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw)
//         {

//         }
//         public override void QueryPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw, long timeOutMs
//                         , Action<byte[]> succAction, Action timeOutAction)
//         {

//         }

//         public override void SendHost(SessionId sessionId, byte[] raw)
//         {
//             if (_host != null)
//                 Net.Send(HandlerId, 0, _host.ConnectionId, raw);
//         }
//         public override void QueryHost(SessionId sessionId, byte[] raw, long timeOutMs
//                         , Action<byte[]> succAction, Action timeOutAction)
//         {
//             if (_host != null)
//                 _ = Net.AsyncRequestQuery(HandlerId, _host.ConnectionId, raw, timeOutMs, succAction, timeOutAction);
//         }
//     }
// }