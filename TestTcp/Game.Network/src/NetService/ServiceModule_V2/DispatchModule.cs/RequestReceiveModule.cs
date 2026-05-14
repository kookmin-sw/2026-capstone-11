

using System;
using System.Runtime.Serialization.Formatters;
using System.Xml.Linq;

namespace Game.Network.Service
{
    public class RequestReceiveModule : IServiceModule, INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.RequestReceiver;
        private DispatchMap _map;
        private INetAPI _net;

        public void Init(ServiceContext_V2 context)
        {
            _map = context.Dispatcher;
            _net = context.Net;

            _net.SetReceiveHandler(this);
        }
        // Data
        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            PacketWrapper wrapper = new(raw);

            if (_map.TryDispatch(wrapper.ReadId(), out var registery))
            {
                PacketWrapper result = registery.Handle(connId, wrapper);
                _net.Send(NetEventHandlerId.Constant.RequestReceiver, queryNum, connId, result.Raw);
            }
            else
            {
                PacketWrapper fail = PacketWrapper.MakeWrap(new FailPacket(FailPacket.FailType.NoDispatchRegistery), FailPacket.Meta, FailPacket.Codec);
                _net.Send(NetEventHandlerId.Constant.RequestReceiver, queryNum, connId, fail.Raw);
            }    
        }

    }
}