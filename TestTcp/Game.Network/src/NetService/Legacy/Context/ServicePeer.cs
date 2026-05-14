// using Game.Network.Protocol;

// namespace Game.Network
// {
//     public class ServicePeer
//     {
//         private ConnId _connId;
//         private ConnectionInfo _connInfo;
//         private PingInfo _pingInfo;
//         private AuthenticateInfo _authInfo;
//         private SessionBindInfo _sessionInfo;

//         public ConnId ConnectionId => _connId;
//         public ConnectionInfo Conn => _connInfo;
//         public PingInfo Ping => _pingInfo;
//         public AuthenticateInfo Auth => _authInfo;
//         public SessionBindInfo Session => _sessionInfo;

//         public ServicePeer( ConnId connId,
//                             ConnectionInfo conn, 
//                             PingInfo ping, 
//                             AuthenticateInfo auth, 
//                             SessionBindInfo sessionInfo)
//         {
//             _connId = connId;
//             _connInfo = conn;
//             _pingInfo = ping;
//             _authInfo = auth;
//             _sessionInfo = sessionInfo;
//         }
//     }
// }