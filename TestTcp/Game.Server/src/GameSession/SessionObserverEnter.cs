
using System.Runtime.InteropServices;
using System.Text;
using Game.Network;

namespace Game.Server
{
    public class SessionObserverEnter : INetReceiveEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.ObserverEnter;
        private INetAPI _net;
        private SessionRouter _router;

        public SessionObserverEnter(INetAPI Net, SessionRouter Router)
        {
            _net = Net;
            _router = Router;

            _net.SetReceiveHandler(this);
        }

        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            string key = Encoding.UTF8.GetString(raw);
            if (key != Setting.ObserverKey)
            {
                Log.WriteLog($"[SessionObserver] Wrong Key Entered");
                return;
            }

            if (!_router.TryAdd("Observer" + GameTime.GetNow(), connId))
            {
                Log.WriteLog("[SessionEnter] Fail to Enter Session");
                return;
            }

            _net.Send(NetEventHandlerId.Constant.ObserverEnter, queryNum, connId, Encoding.UTF8.GetBytes("Accepted"));
        }
    }
}