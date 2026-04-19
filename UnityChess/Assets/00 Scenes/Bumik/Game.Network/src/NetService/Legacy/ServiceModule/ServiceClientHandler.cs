
// using Game.Network.Protocol;
// using Game.Server;

// namespace Game.Network
// {
//     public class ServiceClientHandler : ServiceModule, INetEventHandler
//     {
//         public override int HandlerId => NetEventHandlerId.Constant.Service;
//         private Action? _succAction = null;
//         private Action? _timeOutAction = null;

//         public ServiceClientHandler(INetAPI net, ServiceContext context) : base(net, context) { }

//         public void StartService(string IPAddress, int portNum, long expireTimeMs, Action? succAction = null, Action? timeOutAction = null)
//         {
//             _succAction = succAction;
//             _timeOutAction = timeOutAction;

//             _ = Net.ConnectTo(IPAddress, portNum, expireTimeMs);
//         }

//         public void OnHello(ConnId connId, byte[] raw)
//         {
//             _ = RequestServiceEnter(connId);
//         }

//         public void OnDisconnect(ConnId connId, byte[] raw)
//         {
//             if (Context.PeerDictionary.Remove(connId, out var peer))
//             {
//                 foreach (var listener in Context.OutEventListeners)
//                     listener.Invoke(peer);
//             }
//         }

//         private Task RequestServiceEnter(ConnId connId)
//         {
//             return Net.AsyncRequestQuery(
//                 HandlerId,
//                 connId,
//                 ConnectionInfo.Serialize(Context.SelfInfo),
//                 Context.Opt.helloTimeOutMs,

//                 (answerRaw) =>
//                 {
//                     ConnectionInfo? hostInfo = ConnectionInfo.Deserialize(answerRaw);
//                     if (hostInfo == null)
//                     {
//                         _timeOutAction?.Invoke();
//                         return;
//                     }
//                     var pingInfo = new PingInfo(Context.Opt.pingFailCountToDisconnect);
//                     var auth = new AuthenticateInfo(true);
//                     var sessionBindInfo = new SessionBindInfo();
//                     var peer = new ServicePeer(connId, hostInfo, pingInfo, auth, sessionBindInfo);
//                     Context.AddPeer(connId, peer);

//                     foreach (var listener in Context.EnterEventListeners)
//                         listener.Invoke(peer);

//                     _succAction?.Invoke();
//                 },

//                 () => { _timeOutAction?.Invoke(); }
//                 );
//         }
//     }
// }