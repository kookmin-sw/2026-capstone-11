

using System.Net.NetworkInformation;
using System.Net.WebSockets;
using System.Reflection.Emit;
using System.Xml;
using Game.Network.Protocol;

namespace Game.Network
{
    public class ServicePeer
    {
        private ConnectionInfo _connInfo;
        private PingInfo _pingInfo;
        private AuthenticateInfo _authInfo;
        private SessionBindInfo _sessionbindInfo;


        public ConnectionInfo Conn => _connInfo;
        public PingInfo Ping => _pingInfo;
        public AuthenticateInfo Auth => _authInfo;
        public SessionBindInfo SessionBind => _sessionbindInfo;

        public ServicePeer(ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth, SessionBindInfo sessionBind)
        {
            _connInfo = conn; 
            _pingInfo = ping; 
            _authInfo = auth;
            _sessionbindInfo = sessionBind;
        }
    }

    public class ServiceOption
    {
        public int maxConnPerService;
        public int helloTimeOutMs;
        public int pingIntervalMs;
        public int pingTimeOutMs;
        public int pingFailCountToDisconnect;

        public ServiceOption(
            int MaxConnPerService,
            int HelloTimeOutMs,
            int PingIntervalMs,
            int PingTimeOutMs,
            int PingFailCountToDisconnect
        )
        {
            maxConnPerService = MaxConnPerService;
            helloTimeOutMs = HelloTimeOutMs;
            pingIntervalMs = PingIntervalMs;
            pingTimeOutMs = PingTimeOutMs;
            pingFailCountToDisconnect = PingFailCountToDisconnect;
        }

    }

    public class ServiceContext
    {
        private ConnectionInfo _selfInfo;
        private ServiceOption _opt;
        private Dictionary<string, ServicePeer> _peerDictionary;

        public ServiceContext(ConnectionInfo selfInfo, ServiceOption opt)
        {
            _selfInfo = selfInfo;
            _opt = opt;
            _peerDictionary = new();
        }

        public ConnectionInfo SelfInfo => _selfInfo;
        public Dictionary<string, ServicePeer> PeerDictionary => _peerDictionary;
        public ServiceOption Opt => _opt;
        public bool TryGetPeer(string connId, out ServicePeer info)
            => _peerDictionary.TryGetValue(connId, out info);

        public void Add(string connId, ServicePeer info)
            => _peerDictionary.Add(connId, info);

        public void Add(string connId, ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth, SessionBindInfo sessionBind)
            => _peerDictionary.Add(connId, new ServicePeer(conn, ping, auth, sessionBind));

        public void Remove(string connId)
        { if (_peerDictionary.ContainsKey(connId)) _peerDictionary.Remove(connId); }

        public string GetState()
        {
            var sb = new System.Text.StringBuilder();

            sb.AppendLine("[ServiceContext]");
            sb.AppendLine("\t[SelfInfo]");
            sb.AppendLine("\t\tnetworkType=" + _selfInfo.networkType);
            sb.AppendLine("\t\tconnectionType=" + _selfInfo.connectionType);
            sb.AppendLine("\t\tsessionId=" + _selfInfo.sessionId);
            sb.AppendLine("\t\taccountId=" + _selfInfo.accountId);
            sb.AppendLine("\t\taccountName=" + _selfInfo.playerPlatformId);
            sb.AppendLine("\t\tappVersion=" + _selfInfo.appVersion);
            sb.AppendLine("\t\ttoken=" + _selfInfo.token);

            sb.AppendLine("\t[Option]");
            sb.AppendLine("\t\tmaxConnPerService=" + _opt.maxConnPerService);
            sb.AppendLine("\t\thelloTimeOutMs=" + _opt.helloTimeOutMs);
            sb.AppendLine("\t\tpingIntervalMs=" + _opt.pingIntervalMs);
            sb.AppendLine("\t\tpingFailCountToDisconnect=" + _opt.pingFailCountToDisconnect);

            sb.AppendLine("\t[InfoPage]");
            sb.AppendLine("\t\tCount=" + _peerDictionary.Count);

            foreach (var pair in _peerDictionary)
            {
                string connId = pair.Key;
                ServicePeer info = pair.Value;

                sb.AppendLine("\t\t[ConnId=" + connId + "]");

                sb.AppendLine("\t\t\t[Conn]");
                sb.AppendLine("\t\t\t\tnetworkType=" + info.Conn.networkType);
                sb.AppendLine("\t\t\t\tconnectionType=" + info.Conn.connectionType);
                sb.AppendLine("\t\t\t\tsessionId=" + info.Conn.sessionId);
                sb.AppendLine("\t\t\t\taccountId=" + info.Conn.accountId);
                sb.AppendLine("\t\t\t\taccountName=" + info.Conn.playerPlatformId);
                sb.AppendLine("\t\t\t\tappVersion=" + info.Conn.appVersion);
                sb.AppendLine("\t\t\t\ttoken=" + info.Conn.token);

                sb.AppendLine("\t\t\t[Ping]");
                sb.AppendLine("\t\t\t\tcurrentPingResult=" + info.Ping.currentPingResult);
                sb.AppendLine("\t\t\t\tlastPingTime=" + info.Ping.lastPingTime);
                sb.AppendLine("\t\t\t\tfailureCount=" + info.Ping.failureCount);

                sb.AppendLine("\t\t\t[Auth]");
                sb.AppendLine("\t\t\t\tIsAuth=" + info.Auth.IsAuth);
                sb.AppendLine("\t\t\t\tFailMsg=" + info.Auth.FailMsg);
            }

            return sb.ToString();
        }

    }
}