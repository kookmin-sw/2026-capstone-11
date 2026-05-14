

// using System.Linq.Expressions;
// using System.Net.NetworkInformation;
// using System.Net.WebSockets;
// using System.Reflection.Emit;
// using System.Xml;
// using Game.Network.Protocol;

// namespace Game.Network
// {
//     public class ServiceContext
//     {
//         private ConnectionInfo _selfInfo;
//         private ServiceOption _opt;
//         private Dictionary<ConnId, ServicePeer> _peerDictionary = new(); // (ConnId, ServicePeer)
//         private List<Action<ServicePeer>> _peerEnterListener = new();
//         private List<Action<ServicePeer>> _peerOutListener = new();
//         public ServiceContext(ConnectionInfo selfInfo, ServiceOption opt)
//         {
//             _selfInfo = selfInfo;
//             _opt = opt;
//         }

//         public ConnectionInfo SelfInfo => _selfInfo;
//         public ServiceOption Opt => _opt;
//         public Dictionary<ConnId, ServicePeer> PeerDictionary => _peerDictionary;
//         public List<Action<ServicePeer>> EnterEventListeners => _peerEnterListener;
//         public List<Action<ServicePeer>> OutEventListeners => _peerOutListener;
        

//         public bool TryGetPeer(ConnId connId, out ServicePeer peer)
//             => _peerDictionary.TryGetValue(connId, out peer);

//         public void AddPeer(ConnId connId, ServicePeer info)
//         {
//             _peerDictionary.Add(connId, info);
//         }

//         public void AddPeer(ConnId connId, ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth, SessionBindInfo sessionInfo)
//         {
//             var peer = new ServicePeer(connId, conn, ping, auth, sessionInfo);
//             _peerDictionary.Add(connId, peer);

//         }
//         public void RemovePeer(ConnId connId)
//         {
//             _peerDictionary.Remove(connId, out var peer);
//         }

//         public void AddPeerEnterListener(Action<ServicePeer> listener)
//             => _peerEnterListener.Add(listener);

//         public void RemovePeerEnterListener(Action<ServicePeer> listener)
//             => _peerEnterListener.Remove(listener);

//         public void AddPeerOutListener(Action<ServicePeer> listener)
//             => _peerOutListener.Add(listener);

//         public void RemovePeerOutListener(Action<ServicePeer> listener)
//             => _peerOutListener.Remove(listener);

//         public string GetState()
//         {
//             var sb = new System.Text.StringBuilder();

//             sb.AppendLine("[ServiceContext]");
//             sb.AppendLine("\t[SelfInfo]");
//             sb.AppendLine("\t\tnetworkType=" + _selfInfo.networkType);
//             sb.AppendLine("\t\tconnectionType=" + _selfInfo.connectionType);
//             sb.AppendLine("\t\tsessionId=" + _selfInfo.sessionId);
//             sb.AppendLine("\t\taccountId=" + _selfInfo.accountId);
//             sb.AppendLine("\t\taccountName=" + _selfInfo.playerPlatformId);
//             sb.AppendLine("\t\tappVersion=" + _selfInfo.appVersion);
//             sb.AppendLine("\t\ttoken=" + _selfInfo.token);

//             sb.AppendLine("\t[Option]");
//             sb.AppendLine("\t\tmaxConnPerService=" + _opt.maxConnPerService);
//             sb.AppendLine("\t\thelloTimeOutMs=" + _opt.helloTimeOutMs);
//             sb.AppendLine("\t\tpingIntervalMs=" + _opt.pingIntervalMs);
//             sb.AppendLine("\t\tpingFailCountToDisconnect=" + _opt.pingFailCountToDisconnect);

//             sb.AppendLine("\t[InfoPage]");
//             sb.AppendLine("\t\tCount=" + _peerDictionary.Count);

//             foreach (var pair in _peerDictionary)
//             {
//                 ConnId connId = pair.Key;
//                 ServicePeer info = pair.Value;

//                 sb.AppendLine("\t\t[ConnId=" + connId + "]");

//                 sb.AppendLine("\t\t\t[Conn]");
//                 sb.AppendLine("\t\t\t\tnetworkType=" + info.Conn.networkType);
//                 sb.AppendLine("\t\t\t\tconnectionType=" + info.Conn.connectionType);
//                 sb.AppendLine("\t\t\t\tsessionId=" + info.Conn.sessionId);
//                 sb.AppendLine("\t\t\t\taccountId=" + info.Conn.accountId);
//                 sb.AppendLine("\t\t\t\taccountName=" + info.Conn.playerPlatformId);
//                 sb.AppendLine("\t\t\t\tappVersion=" + info.Conn.appVersion);
//                 sb.AppendLine("\t\t\t\ttoken=" + info.Conn.token);

//                 sb.AppendLine("\t\t\t[Ping]");
//                 sb.AppendLine("\t\t\t\tcurrentPingResult=" + info.Ping.currentPingResult);
//                 sb.AppendLine("\t\t\t\tfailureCount=" + info.Ping.failureCount);

//                 sb.AppendLine("\t\t\t[Auth]");
//                 sb.AppendLine("\t\t\t\tIsAuth=" + info.Auth.IsAuth);
//                 sb.AppendLine("\t\t\t\tFailMsg=" + info.Auth.FailMsg);
//             }

//             return sb.ToString();
//         }

//     }
// }