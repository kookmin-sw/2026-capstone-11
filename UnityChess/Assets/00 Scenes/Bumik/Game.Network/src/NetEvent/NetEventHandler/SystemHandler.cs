

using System;
using System.Collections.Generic;
using Game.Network.Protocol;

namespace Game.Network
{

    public class SystemHandler : INetEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.System;
        private INetAPI _net;
        private HashSet<ConnId> _validConnIdList;

        public SystemHandler(INetAPI net)
        {
            _net = net;
            _validConnIdList = new();
        }

        public void OnDisconnect(ConnId connId, byte[] raw)
        {
            Log.WriteLog($"[System]: Disconnection Finished |  Connect ( {connId} )");
            _validConnIdList.Remove(connId);
        }

        public void OnException(ConnId connId, byte[] raw, string msg)
        {
            Log.WriteLog($"[System]: Exception Happen ( {msg} )");

            if (_validConnIdList.Contains(connId))
            {
                _net.Disconnect(connId);
                Log.WriteLog($"[System]: Publish Disconnect Event ( {connId} )");
            }
        }

        public void OnHello(ConnId connId, byte[] raw)
        {
            Log.WriteLog($"[System]: New Connection ( {connId} )");

            _validConnIdList.Add(connId);
        }

        public void OnReceive(ConnId connId, byte[] raw)
        {
            Log.WriteLog($"[System]: New Message Received From ( {connId} ) | Content ( {BitConverter.ToString(raw)} )");
        }


    };
}