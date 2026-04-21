namespace Game.Network.Service
{
    public class PongModule : IServiceModule, INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.PingPong;
        private INetAPI _net;
        public void Init(ServiceContext_V2 context_V2)
        {
            _net = context_V2.Net;
            _net.SetReceiveHandler(this);
        }

        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            _net.Send(NetEventHandlerId.Constant.PingPong, queryNum, connId, Array.Empty<byte>());
        }
    }
}