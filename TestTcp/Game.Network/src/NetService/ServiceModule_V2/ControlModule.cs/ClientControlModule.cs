
using System.ComponentModel;

namespace Game.Network.Service
{
    public class ClientControlModule : IServiceModule, INetControlEventHandler
    {
        private IHostWriter _host;
        private IPeerDictWriter _other;
        private IServiceEventPublisher _bridge;
        private ISelfWriter _self;
        private INetAPI _net;

        private int _suspendTimeOutThres;
        private int _disconnectTimeOutThres;
        
        public void Init(ServiceContext_V2 context)
        {
            _host = context.Host;
            _other = context.Other;
            _bridge = context.EventBridge;
            _self = context.Self;
            _net = context.Net;

            _suspendTimeOutThres = context.Opt.suspendTimeOutThres;
            _disconnectTimeOutThres = context.Opt.disconnectTimeOutThres;
            
            context.Net.SetControlHandler(this);
        }

        public PeerEnterReq Request()
        {
            return new PeerEnterReq(_self.connWriter.instance);
        }

        public void OnRespond(ConnId id, PeerEnterRsp rsp)
        {
            if (_other.HasPeer(id)) return;
            
            Peer peer = new Peer(id, rsp.RemotePeerInfo);

            _other.AddPeer(peer);
            _bridge.PublishEnterEvents(peer);
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



        public void OnHello(ConnId connId, byte[] raw)
        {
            if (_host.HasHost)
            {
                Log.WriteLog($"[ClientControl] : 호스트 연결 중, 추가적인 호스트 연결 발생. 호스트 오버라이드");
            }
            Log.WriteLog($"[ClientControl] : 호스트 등록 : {connId}");
            _host.SetHost(connId);
        }
        public void OnDisconnect(ConnId connId, byte[] raw)
        {
            Log.WriteLog($"[ClientControl] : 호스트 연결 해제");
            _host.Clear();
        }

    }
}