

using System.Net.NetworkInformation;
using System.Net.WebSockets;
using System.Reflection.Emit;
using Game.Network.Protocol;

namespace Game.Network
{
    public class ServiceInfo
    {
        private ConnectionInfo _connInfo;
        private PingInfo _pingInfo;
        private AuthenticateInfo _authInfo;

        public ConnectionInfo Conn => _connInfo;
        public PingInfo Ping => _pingInfo;
        public AuthenticateInfo Auth => _authInfo;

        public ServiceInfo(ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth)
        { _connInfo = conn; _pingInfo = ping; _authInfo = auth; }
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
        private Dictionary<string, ServiceInfo> _infoPage;
        private ServiceOption _opt;

        public ServiceContext(ConnectionInfo selfInfo, ServiceOption opt)
        {
            _selfInfo = selfInfo;
            _infoPage = new();
            _opt = opt;
        }

        public ConnectionInfo SelfInfo => _selfInfo;
        public Dictionary<string, ServiceInfo> InfoDictionary => _infoPage;
        public ServiceOption Opt => _opt;
        public bool TryGetInfo(string connId, out ServiceInfo info)
            => _infoPage.TryGetValue(connId, out info);

        public void Add(string connId, ServiceInfo info)
            => _infoPage.Add(connId, info);

        public void Add(string connId, ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth)
            => _infoPage.Add(connId, new ServiceInfo(conn, ping, auth));

        public void Remove(string connId)
        { if (_infoPage.ContainsKey(connId)) _infoPage.Remove(connId); }

        public string GetState()
        {
            var sb = new System.Text.StringBuilder();

            sb.AppendLine("[ServiceContext]");
            sb.AppendLine("\t[SelfInfo]");
            sb.AppendLine("\t\tnetworkType=" + _selfInfo.networkType);
            sb.AppendLine("\t\tconnectionType=" + _selfInfo.connectionType);
            sb.AppendLine("\t\tsessionId=" + _selfInfo.sessionId);
            sb.AppendLine("\t\taccountId=" + _selfInfo.accountId);
            sb.AppendLine("\t\taccountName=" + _selfInfo.accountName);
            sb.AppendLine("\t\tappVersion=" + _selfInfo.appVersion);
            sb.AppendLine("\t\ttoken=" + _selfInfo.token);

            sb.AppendLine("\t[Option]");
            sb.AppendLine("\t\tmaxConnPerService=" + _opt.maxConnPerService);
            sb.AppendLine("\t\thelloTimeOutMs=" + _opt.helloTimeOutMs);
            sb.AppendLine("\t\tpingIntervalMs=" + _opt.pingIntervalMs);
            sb.AppendLine("\t\tpingFailCountToDisconnect=" + _opt.pingFailCountToDisconnect);

            sb.AppendLine("\t[InfoPage]");
            sb.AppendLine("\t\tCount=" + _infoPage.Count);

            foreach (var pair in _infoPage)
            {
                string connId = pair.Key;
                ServiceInfo info = pair.Value;

                sb.AppendLine("\t\t[ConnId=" + connId + "]");

                sb.AppendLine("\t\t\t[Conn]");
                sb.AppendLine("\t\t\t\tnetworkType=" + info.Conn.networkType);
                sb.AppendLine("\t\t\t\tconnectionType=" + info.Conn.connectionType);
                sb.AppendLine("\t\t\t\tsessionId=" + info.Conn.sessionId);
                sb.AppendLine("\t\t\t\taccountId=" + info.Conn.accountId);
                sb.AppendLine("\t\t\t\taccountName=" + info.Conn.accountName);
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