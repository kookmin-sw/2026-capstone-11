

using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using Game.Network;
using Game.Server.Chess;
using SeaEngine.GameDataManager.Components;

namespace Game.Server
{


    public class Session : INetEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.GameMessage;

        public SessionEvents Events = new();
        private SessionRouter _router = new();
        private SessionEnter _entrance;
        private INetAPI _net;

        public Session(INetAPI net)
        {
            _net = net;
            _net.SetControlHandler(this);
            _net.SetReceiveHandler(this);

            _entrance = new(_net, Events, _router);
        }

        public void QueryPlayer(string playerName, byte[] raw, long expireTimeMs, Action<string, QueryTaskResult> callBack)
        {
            if (_router.TryRoute(playerName, out var connId))
            {
                _net.AsyncRequestQuery(
                     HandlerId,
                     connId,
                     raw,
                     expireTimeMs,
                     (connId, result) => { callBack(playerName, result); }
                     );
                return;
            }
            else return;
        }
        public void BroadCastPlayer(byte[] raw)
        {
            foreach (var connId in _router.IdList)
                _net.Send(HandlerId, 0, connId, raw);

        }
        public void SendPlayer(string playerName, byte[] raw)
        {
            if (_router.TryRoute(playerName, out var connId))
                _net.Send(HandlerId, 0, connId, raw);
        }

        public void Clear()
        {
            foreach (var conn in _router.IdList)
                _net.Disconnect(conn);

            Events.Clear();
            _router.Clear();
        }
        // Data
        public void OnReceive(ConnId connId, byte[] raw)
        {
            if (_router.TryRoute(connId, out string name))
                Events.OnGetMessage?.Invoke(name, raw);
        }
        public void OnRespond(ConnId connId, int queryNum, byte[] raw)
        {
            if (_router.TryRoute(connId, out string name))
                Events.OnGetResponse?.Invoke(name, raw);
        }
        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            if (_router.TryRoute(connId, out string name) && Events.OnGetQuery != null)
            {
                byte[] rsp = Events.OnGetQuery(name, raw);
                if (rsp == null ) rsp = Array.Empty<byte>();

                _net.Send(HandlerId, queryNum, connId, rsp);
            }
        }

        // Control
        public void OnException(ConnId connId, byte[] raw, string msg)
            => DisconnectAndEvent(connId);

        public void OnDisconnect(ConnId connId, byte[] raw)
            => DisconnectAndEvent(connId);

        private void DisconnectAndEvent(ConnId connId)
        {
            if (_router.TryRoute(connId, out var name) && _router.TryRemove(connId))
            {
                Events.OnPlayerExit?.Invoke(name);
            }
        }

    };
}