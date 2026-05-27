// using System.ComponentModel;
// using System.IO.Compression;
// using Game.Network;
// using Game.Network.Protocol;

// namespace Game.Server
// {

//     public class ServiceHostHandler : ServiceModule, INetEventHandler
//     {
//         public override int HandlerId => NetEventHandlerId.Constant.Service;

//         public ServiceHostHandler(INetAPI net, ServiceContext context) : base(net, context) { }

//         public void OnQuery(ConnId connId, int queryNum, byte[] raw)
//         {
//             //TODO: Service Key 인증

//             // Deserialize raw -> 
//             try
//             {
//                 PacketReader reader = new(raw);
//                 var connInfo = ConnectionInfo.Codec.Read(ref reader);

//                 var pingInfo = new PingInfo(Context.Opt.pingFailCountToDisconnect);
//                 var auth = new AuthenticateInfo(true);
//                 var sessionBindInfo = new SessionBindInfo();

//                 var peer = new ServicePeer(connId, connInfo, pingInfo, auth, sessionBindInfo);
//                 Context.AddPeer(connId, peer);

//                 foreach (var listener in Context.EnterEventListeners)
//                     listener.Invoke(peer);

//                 Net.Send(HandlerId, queryNum, connId, ConnectionInfo.Serialize(Context.SelfInfo));
//             }
//             catch (InvalidOperationException e)
//             {
//                 Log.WriteLog("[Service]: Fail to Deserialize connInfo");
//                 Net.Send(HandlerId, queryNum, connId, ConnectionInfo.Serialize(Context.SelfInfo));
//                 return;
//             }

//         }


//         public void OnDisconnect(ConnId connId, byte[] raw)
//         {
//             if (Context.PeerDictionary.Remove(connId, out var peer))
//             {
//                 foreach (var listener in Context.OutEventListeners)
//                     listener.Invoke(peer);
//             }
//         }



//     };
// }