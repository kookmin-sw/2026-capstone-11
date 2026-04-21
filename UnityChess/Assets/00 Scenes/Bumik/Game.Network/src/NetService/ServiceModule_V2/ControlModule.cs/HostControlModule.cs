using System.ComponentModel.Design;

namespace Game.Network.Service
{
    public class HostControlModule : IServiceModule, INetControlEventHandler
    {
        private IPeerDictWriter _other;
        private IServiceEventPublisher _bridge;


        public void Init(ServiceContext_V2 context)
        {
            _other = context.Other;
            _bridge = context.EventBridge;
            context.Net.SetControlHandler(this);
        }

        public void OnException(ConnId connId, byte[] raw, string msg) { }

        public void OnHello(ConnId connId, byte[] raw)
        {

        }
        public void OnDisconnect(ConnId connId, byte[] raw)
        {
            if (_other.RemovePeer(connId, out var Peer))
            {
                Log.WriteLog($"[HostControl] : Peer Disconnected {connId} | Publish Out Event");
                _bridge.PublishOutEvents(Peer);
            }
        }

    }
}