
using System;

namespace Game.Network.Service
{
    public class ClientService
    {
        private ServiceManager _manager;
        private ClientControlModule _clientControl;
        private RequestSendModule _sendModule;

        
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
            _manager.AddModule<RequestSendModule>();
            _manager.AddModule<PingModule_V2>();
            _manager.AddModule<PongModule>();
            _manager.AddModule<SessionReqModule>();

            _clientControl = _manager.GetModule<ClientControlModule>();
            _sendModule = _manager.GetModule<RequestSendModule>();
        }

        public string GetState() => _manager.GetState();

        public void Tick(int delta)
            =>  _manager.Tick(delta);


        public void RequestPeerEnter(Action<PeerEnterRsp> succ, Action<string> fail, long expireTimeMs)
        {
            _sendModule.SendRequest(
                _clientControl.Request(),
                PeerEnterReq.Meta,
                PeerEnterReq.Codec,
                _clientControl.OnRespond,
                succ,
                fail,
                PeerEnterRsp.Meta,
                PeerEnterRsp.Codec,
                expireTimeMs
            );
        }

    }
}