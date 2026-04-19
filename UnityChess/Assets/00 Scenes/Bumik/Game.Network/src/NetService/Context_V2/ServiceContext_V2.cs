namespace Game.Network.Service
{
    public class SecurityKeyHolder
    {

    };

    public class DumpedPeerDictionary
    {

    };


    public class ServiceContext_V2
    {
        public INetAPI Net { get; }
        public SelfInfo Self { get; }
        public ServiceOption Opt { get; }
        public PeerDictionary Other { get; }
        public HostHolder Host { get; }
        //public SecurityKeyHolder Security {get;}
        public RunningGames Games { get; }
        public RoutingMap Router { get; }
        public ServiceEventBridge EventBridge { get; }

        public ServiceContext_V2(INetAPI net,
                                ISessionBuilder builder,
                                ISessionPort port,
                                ConnInfo selfConnInfo,
                                ServiceOption opt)
        {
            Net = net;
            Opt = opt;
            Self = new(selfConnInfo);
            Other = new();
            Host = new();
            Games = new(builder, port);
            Router = new();
            EventBridge = new();
        }

        public string GetState()
        {
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("[ServiceContext]");
            sb.AppendLine($"  Host     : {(Host.HasHost ? Host.connId.ToString() : "None")}");
            sb.AppendLine($"  Self     : {Self.connInfo.networkType} / {Self.connInfo.connectionType}");
            sb.AppendLine($"  Peers    : {Other.ReadPeers().Count}");
            sb.AppendLine($"  Sessions : {Games.ActiveSessionCount}");
            sb.AppendLine($"  Routes   : {Router.RouteCount}");
            return sb.ToString();
        }
    }

}