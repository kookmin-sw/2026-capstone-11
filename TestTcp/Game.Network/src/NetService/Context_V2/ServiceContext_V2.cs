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
        public INetAPI Net {get;}
        public SelfInfo Self {get;}
        public ServiceOption Opt {get;}
        public PeerDictionary Other {get;}
        public HostHolder Host {get;}
        //public SecurityKeyHolder Security {get;}
        public RunningGames Games {get;}
        public RoutingMap Router {get;}
        public ServiceEventBridge EventBridge {get;} 

        public ServiceContext_V2(INetAPI net, ServiceOption opt)
        {
            Net = net;
            Opt = opt;
            Self = new();
            Other = new();
            Host = new();
            Router = new();
            EventBridge = new();
        }
    }

}