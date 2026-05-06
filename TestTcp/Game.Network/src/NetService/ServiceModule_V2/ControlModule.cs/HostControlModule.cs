using System.ComponentModel.Design;

namespace Game.Network.Service
{
    public class HostControlModule : IServiceModule
                                    , INetReceiveEventHandler

    {
        public int HandlerId => NetEventHandlerId.Constant.PeerEntrance;


        private IPeerDictWriter _other;
        private INetAPI _net;
        private IServiceEventPublisher _bridge;

        private int SuspendTimeOutThres;
        private int DisconnectTimeOutThres;

        public void Init(ServiceContext_V2 context)
        {
            _net = context.Net;
            _other = context.Other;
            _bridge = context.EventBridge;
        }

        public void Tick(int delta)
        {
            foreach (var peer in _other.PeerWriterList())
            {
                peer.AddTimer(delta);
                if (peer.Timer > SuspendTimeOutThres && peer.state == Peer.State.Connected)
                {
                    peer.SetState(Peer.State.Suspended);
                    _net.Disconnect(peer.connId);
                }
                if (peer.Timer > DisconnectTimeOutThres && peer.state == Peer.State.Suspended)
                {
                    peer.SetState(Peer.State.Finished);
                    _bridge.PublishOutEvents(peer);
                }
            }
        }
    }
}