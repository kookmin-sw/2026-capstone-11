
using System.Runtime.InteropServices;
using System.Text;
using Game.Network;

namespace Game.Server
{
    public class SessionEnter : INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.PeerEntrance;
        private INetAPI _net;
        private SessionEvents _events;
        private SessionRouter _router;

        public SessionEnter(INetAPI Net, SessionEvents Events, SessionRouter Router)
        {
            _net = Net;
            _events = Events;
            _router = Router;

            _net.SetReceiveHandler(this);
        }

        public void OnReceive(ConnId connId, byte[] raw) {}
        public void OnRespond(ConnId connId, int queryNum, byte[] raw) {}
        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            string name = Encoding.UTF8.GetString(raw);
            if (String.IsNullOrEmpty(name)) 
            {
                Log.WriteLog($"[SessionEnter] Wrong Name from {connId}");
                return;
            }

            if (!_router.TryAdd(name, connId))
            {
                Log.WriteLog("[SessionEnter] Fail to Enter Session");
                return;
            }

            _events.OnPlayerEnter?.Invoke(name);
        }
    }

}