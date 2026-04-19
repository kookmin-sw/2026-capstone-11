using System;

namespace Game.Network.Service
{
    public class EnterRequestModule : IServiceModule
                                    , IRequest<PeerEntranceReq, PeerEntranceRsp>
    {
        private INetAPI _net;
        private IHostReader _host;
        private ISelfWriter _self;
        private IPeerDictWriter _other;
        private IServiceEventPublisher _publisher;

        private int _enterTimeOutMs;


        public void Init(ServiceContext_V2 context_V2)
        {
            _net = context_V2.Net;
            _host = context_V2.Host;
            _self = context_V2.Self;
            _other = context_V2.Other;
            _publisher = context_V2.EventBridge;

            _enterTimeOutMs = context_V2.Opt.helloTimeOutMs;
        }

        public void Request(Action<PeerEntranceRsp> succ, Action<string> fail)
            => Request(new PeerEntranceReq(_self.connWriter.instance), succ, fail);

        public void Request(PeerEntranceReq msg, Action<PeerEntranceRsp> succ, Action<string> fail)
        {
            var payload = new byte[PeerEntranceReq.Codec.GetSize(msg)];
            var writer = new PacketWriter(payload);
            PeerEntranceReq.Codec.Write(ref writer, msg);

            _ = _net.AsyncRequestQuery(NetEventHandlerId.Constant.PeerEntrance, _host.connId, payload, _enterTimeOutMs,
                (connId, result) => EnterCallBack(connId, result, succ, fail));
        }

        private void EnterCallBack(ConnId connId, QueryTaskResult result, Action<PeerEntranceRsp> succ, Action<string> fail)
        {
            
            if (result.IsCancelled)
            {
                fail.Invoke("QuaryCancelled");
            }

            else if (result.IsTimeOut)
            {
                fail.Invoke("TimeOut");
            }

            else if (connId != _host.connId)
            {
                fail.Invoke($"Rsp connId is Different with Host | Host : {_host.connId}, RSPConnId : {connId}");
            }

            else if (result.IsResponded)
            {
                PacketReader reader = new(result.AnswerRaw);
                try
                {
                    var response = PeerEntranceRsp.Codec.Read(ref reader);
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
            return;
        }

    }
}