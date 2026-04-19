
using System.ComponentModel;

namespace Game.Network.Service
{
    public class ClientControlModule : IServiceModule, INetControlEventHandler
    {
        private IHostWriter _host;
        private IPeerDictWriter _other;
        private IServiceEventPublisher _bridge;
        
        public void Init(ServiceContext_V2 context)
        {
            _host = context.Host;
            _other = context.Other;
            _bridge = context.EventBridge;
            
            context.Net.SetControlHandler(this);
        }

        public void OnException(ConnId connId, byte[] raw, string msg) {}

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

            if (_other.RemovePeer(connId, out var Peer))
            {
                Log.WriteLog($"[ClientControl] : Peer Disconnected {connId} | Publish Out Event");
                _bridge.PublishOutEvents(Peer);
            }
        }

    }
}