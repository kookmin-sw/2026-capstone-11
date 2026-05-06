

using System.Runtime.Serialization.Formatters;

namespace Game.Network.Service
{
    public class RequestDispatchModule : INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.RequestTarget;

        private DispatchMap _map;
        private INetAPI _net;

        void Init(ServiceContext_V2 context)
        {
            _map = context.Dispatcher;
            _net = context.Net;
        }
        // Data
        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            if (raw.Length < 4)
            {
                var rsp = new FailRsp(FailRsp.FailType.FailDeserialize);
                var buffer = new byte[FailRsp.Codec.GetSize(rsp) + 1]; 
                PacketWriter writer = new(buffer);
                FailRsp.Codec.Write(ref writer, rsp);

                _net.Send(HandlerId, queryNum, connId, buffer);
            }
        }

    }
}