
namespace Game.Network.Service
{
    public class ClientService
    {
        private ServiceManager _manager;

        
        public ClientService(INetAPI net, 
                            ISessionBuilder sessionBuilder, 
                            ISessionPort port,
                            string PlayerDisplayName, 
                            string AccountId,
                            string AppVersion,
                            ServiceOption opt)
        {
            var selfConnInfo = new ConnInfo(Protocol.NetworkType.Dedicated, 
                                            Protocol.ConnectionType.Client,
                                            PlayerDisplayName,
                                            AccountId,
                                            AppVersion);
            _manager = new(net, sessionBuilder, port, selfConnInfo, opt);

            _manager.AddModule<ClientControlModule>();
            _manager.AddModule<PingModule_V2>();
            _manager.AddModule<PongModule>();
            _manager.AddModule<SessionReqModule>();
            _manager.AddModule<EnterRequestModule>();
        }

        public string GetState() => _manager.GetState();

        public void Tick(int delta)
            =>  _manager.Tick(delta);

        public EnterRequestModule PeerEnter
            => _manager.GetModule<EnterRequestModule>();

        public IRequest<SessionReq, SessionRsp> Session
            =>  _manager.GetModule<SessionReqModule>();

    }
}