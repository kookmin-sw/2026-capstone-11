using System.Linq.Expressions;
using System.Text;
using Game.Network;
using Game.Network.Service;

namespace Game.Server
{
    public class SessionReady : INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.GameReady;
        private INetAPI _net;
        private SessionEvents _events;
        private SessionRouter _router;

        public SessionReady(INetAPI Net, SessionEvents Events, SessionRouter Router)
        {
            _net = Net;
            _events = Events;
            _router = Router;

            _net.SetReceiveHandler(this);
        }

        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            try
            {
                if (_router.TryRoute(connId, out string name) && _events.OnSessionPlayerReady != null)
                {
                    PacketReader reader = new(raw);
                    var req = SimpleReq.Codec.Read(ref reader);

                    SimpleRsp rsp = _events.OnSessionPlayerReady(name, req);

                    byte[] buffer = new byte[SimpleRsp.Codec.GetSize(rsp)];
                    PacketWriter writer = new(buffer);
                    SimpleRsp.Codec.Write(ref writer, rsp);

                    _net.Send(HandlerId, queryNum, connId, buffer);
                }
                else
                {
                    SimpleRsp deny = SimpleRsp.Denied($"No Session To Handle Req");

                    byte[] buffer = new byte[SimpleRsp.Codec.GetSize(deny)];
                    PacketWriter writer = new(buffer);
                    SimpleRsp.Codec.Write(ref writer, deny);

                    _net.Send(HandlerId, queryNum, connId, buffer);
                }
            }
            catch (Exception e)
            {
                SimpleRsp error = SimpleRsp.Denied($"Server Exception Happen {e.Message}");

                byte[] buffer = new byte[SimpleRsp.Codec.GetSize(error)];
                PacketWriter writer = new(buffer);
                SimpleRsp.Codec.Write(ref writer, error);

                _net.Send(HandlerId, queryNum, connId, buffer);
            }
        }
    }
}