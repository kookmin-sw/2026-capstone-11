
// using System.Data.Common;
// using System.Diagnostics.CodeAnalysis;
// using System.Net.WebSockets;
// using System.Reflection;
// using System.Text;
// using Game.Network.Protocol;

// namespace Game.Network
// {
//     public abstract class SessionModule : ServiceModule, ISessionPort
//     {
//         public override int HandlerId => NetEventHandlerId.Constant.Session;
//         public static byte[] RejectedMSG => Encoding.UTF8.GetBytes("Rejected");
//         public static byte[] AcceptedMSG => Encoding.UTF8.GetBytes("Accepted");
//         public static bool IsAcceptMSG(byte[] raw) 
//             => AcceptedMSG == raw;


//         protected Dictionary<SessionId, Session> _activeSession = new();
//         protected ISessionBuilder _builder;
        

//         public SessionModule(INetAPI net, ServiceContext context, ISessionBuilder builder) : base(net, context)
//         {_builder = builder;}

//         public bool JoinAndInvokeSession(ServicePeer peer)
//         {
//             if (!JoinToSession(peer)) return false;
        
//             peer.Session.session?.OnPlayerEnter?.Invoke(peer.Session.playerId);
//             return true;
//         }
//         public bool ExitAndInvokeSession(ServicePeer peer)
//         {
//             var session = peer.Session.session;
//             var playerId = peer.Session.playerId;

//             if (!ExitToSession(peer)) return false;

//             session?.OnPlayerExit?.Invoke(playerId);
//             return true;
            
//         }
//         protected virtual bool JoinToSession(ServicePeer peer)
//         {
//             // 세션에 바인드 되지 않음
//             if (!peer.Session.IsSessionBinded) return false;

//             // 세션 재연결
//             if (peer.Session.IsSessionEntered)
//             {
//                 // TODO: 재연결 매커니즘 추가
//                 return true;
//             }

//             // 생성된 세션 참가
//             if (_activeSession.TryGetValue(peer.Session.sessionId, out var active))
//             {
//                 if (!active.TryAddPlayer(out var id) || id == null) return false;
//                 peer.Session.IsSessionEntered = true;
//                 peer.Session.playerId = id.Value;
//                 peer.Session.session = active;

//                 return true;
//             }

//             // 새 세션 생성
//             if (TryBuildSession(peer.Session.sessionId, out var created) && created != null)
//             {
//                 // 플레이어 등록
//                 if (!created.TryAddPlayer(out var id) || id == null)
//                 {
//                     _activeSession.Remove(created.SessionId);
//                     return false;
//                 }
//                 peer.Session.IsSessionEntered = true;
//                 peer.Session.playerId = id.Value;
//                 peer.Session.session = created;
                
//                 return true;
//             }

//             // 새 세션 생성 실패
//             return false;
//         }

//         /// <summary>
//         /// Don't Call this fn when disconnect unsafe
//         /// </summary>
//         /// <param name="peer"></param>
//         /// <returns></returns>
//         protected virtual bool ExitToSession(ServicePeer peer)
//         {
//             // 세션에 참가되지 않은 peer 
//             if (!peer.Session.IsSessionBinded || !peer.Session.IsSessionEntered) return false;

//             if (!_activeSession.TryGetValue(peer.Session.sessionId, out var session)) return false;

//             if (!session.RemovePlayer(peer.Session.playerId)) return false;

//             peer.Session.IsSessionBinded = false;
//             peer.Session.IsSessionEntered = false;
//             peer.Session.session = null;

//             return true;
//         }

//         public abstract void SendPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw);
//         public abstract void QueryPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction);
//         public abstract void SendHost(SessionId sessionId, byte[] raw);
//         public abstract void QueryHost(SessionId sessionId, byte[] raw, long timeOutMs, Action<byte[]> succAction, Action timeOutAction);

//         protected bool TryBuildSession(SessionId id, out Session? session)
//         {
//             if (_activeSession.Count >= Context.Opt.maxSessionPerService)
//             {
//                 session = null;
//                 return false;
//             }

//             session = _builder.BuildSession((ISessionPort) this, id);

//             if (session == null) return false;

//             _activeSession.Add(id, session);
//             return true;
//         }


//     }
// }
