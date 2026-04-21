namespace Game.Network.Service
{
    public class EnterRequestModule : IServiceModule
                                    , IRequest<PeerEntranceRequest, PeerEntranceResponse>
    {
        private INetAPI _net;
        private IHostReader _host;
        private ISelfWriter _self;
        private IPeerDictWriter _other;
        private IServiceEventPublisher _publisher;

        private int _enterTimeOutMs;
        private bool _onRequest = false;



        public void Init(ServiceContext_V2 context_V2)
        {
            _net = context_V2.Net;
            _host = context_V2.Host;
            _self = context_V2.Self;
            _other = context_V2.Other;
            _publisher = context_V2.EventBridge;

            _enterTimeOutMs = context_V2.Opt.helloTimeOutMs;
        }

        public void Request(Action<PeerEntranceResponse> succ, Action<string> fail)
            => Request(new PeerEntranceRequest(_self.connWriter.instance), succ, fail);

        public void Request(PeerEntranceRequest msg, Action<PeerEntranceResponse> succ, Action<string> fail)
        {
            if (_onRequest) return;

            _onRequest = true;
            var payload = new byte[PeerEntranceRequest.Codec.GetSize(msg)];
            var writer = new PacketWriter(payload);
            PeerEntranceRequest.Codec.Write(ref writer, msg);

            _ = _net.AsyncRequestQuery(NetEventHandlerId.Constant.PeerEntrance, _host.connId, payload, _enterTimeOutMs,
                (connId, result) => EnterCallBack(connId, result, succ, fail));
        }

        private void EnterCallBack(ConnId connId, QueryTaskResult result, Action<PeerEntranceResponse> succ, Action<string> fail)
        {
            if (result.IsCancelled || connId != _host.connId)
            {
                fail.Invoke("QuaryCancelled");
            }
            else if (result.IsTimeOut)
            {
                fail.Invoke("TimeOut");
            } 
            else if (result.IsResponded)
            {
                PacketReader reader = new(result.AnswerRaw);
                try
                {
                    var response = PeerEntranceResponse.Codec.Read(ref reader);
                    if (response.IsSucc)
                    {
                        var newPeer = new Peer(connId, response.RemotePeerInfo);
                        _other.AddPeer(newPeer);
                        _publisher.PublishEnterEvents(newPeer);
                    }

                    succ.Invoke(response);
                }
                catch (Exception e)
                {
                    Log.WriteLog($"Exception while processing enter repsonse : {e.Message}");
                    _other.RemovePeer(_host.connId);
                    fail.Invoke("Fail to Process response");
                }
            }
            _onRequest = false;
            return;
        }

    }
}