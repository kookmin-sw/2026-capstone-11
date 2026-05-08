using System.ComponentModel.Design;

namespace Game.Network.Service
{
    public class HostControlModule : IServiceModule
    {

        private IPeerDictWriter _other;
        private ISelfWriter _self;
        private DispatchMap _map;
        private INetAPI _net;
        private IServiceEventPublisher _bridge;

        private int _suspendTimeOutThres;
        private int _disconnectTimeOutThres;

        public void Init(ServiceContext_V2 context)
        {
            _self = context.Self;
            _net = context.Net;
            _other = context.Other;
            _bridge = context.EventBridge;
            _map = context.Dispatcher;

            _suspendTimeOutThres = context.Opt.suspendTimeOutThres;
            _disconnectTimeOutThres = context.Opt.disconnectTimeOutThres;            
            
            _map.Register(HandleEnter, PeerEnterReq.Meta, PeerEnterReq.Codec, PeerEnterRsp.Meta , PeerEnterRsp.Codec);
        }

        public void Tick(int delta)
        {
            foreach (var peer in _other.PeerWriterList())
            {
                peer.AddTimer(delta);
                if (peer.Timer > _suspendTimeOutThres && peer.state == Peer.State.Connected)
                {
                    peer.SetState(Peer.State.Suspended);
                    _net.Disconnect(peer.connId);
                }
                if (peer.Timer > _disconnectTimeOutThres && peer.state == Peer.State.Suspended)
                {
                    peer.SetState(Peer.State.Finished);
                    _bridge.PublishOutEvents(peer);
                }
            }
        }

        private PeerEnterRsp? HandleEnter(ConnId id, PeerEnterReq req)
        {
            if (_other.HasPeer(id)) return null;

            Peer peer = new Peer(id, req.Info);

            _other.AddPeer(id, peer);

            _bridge.PublishEnterEvents(peer);

            return new PeerEnterRsp(_self.connWriter.instance);
        }     
    }
}