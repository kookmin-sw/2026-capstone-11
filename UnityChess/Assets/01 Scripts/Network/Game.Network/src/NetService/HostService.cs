

namespace Game.Network.Service
{
    public class HostService
    {
        private ServiceManager _manager;

        
        public HostService(INetAPI net, 
                            ISessionBuilder sessionBuilder, 
                            ISessionPort port,
                            string PlayerDisplayName, 
                            string AccountId,
                            string AppVersion,
                            ServiceOption opt)
        {
            var selfConnInfo = new ConnInfo(Protocol.NetworkType.Dedicated, 
                                            Protocol.ConnectionType.Host,
                                            PlayerDisplayName,
                                            AccountId,
                                            AppVersion);
            _manager = new(net, sessionBuilder, port, selfConnInfo, opt);

            _manager.AddModule<HostControlModule>();
            _manager.AddModule<EnterResponseModule>();
            _manager.AddModule<PingModule_V2>();
            _manager.AddModule<PongModule>();
            _manager.AddModule<SessionRspModule>();
        }

        public string GetState() => _manager.GetState();
        public void Tick(int delta)
            =>  _manager.Tick(delta);

    }
}