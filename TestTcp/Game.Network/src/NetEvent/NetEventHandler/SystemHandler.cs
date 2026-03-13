

namespace Game.Network
{

    public class SystemHandler : INetEventHandler
    {
        private INetAPI _net;
        private HashSet<string> _validConnIdList;

        public SystemHandler(INetAPI net)
        {
            _net = net;
            _validConnIdList = new();
        }

        public void OnDisconnect(string ConnId, byte[] raw)
        {
            Log.WriteLog($"[System]: Disconnection Finished |  Connect ( {ConnId} )");
            _validConnIdList.Remove(ConnId);
        }

        public void OnException(string ConnId, byte[] raw, string msg)
        {
            Log.WriteLog($"[System]: Exception Happen ( {msg} )");

            if (_validConnIdList.Contains(ConnId))
            {
                _net.Disconnect(ConnId);
                Log.WriteLog($"[System]: Publish Disconnect Event ( {ConnId} )");
            }
        }

        public void OnHello(string ConnId, byte[] raw)
        {
            Log.WriteLog($"[System]: New Connection ( {ConnId} )");

            _validConnIdList.Add(ConnId);
        }

        public void OnReceive(string ConnId, byte[] raw)
        {
            Log.WriteLog($"[System]: New Message Received From ( {ConnId} ) | Content ( {BitConverter.ToString(raw)} )");
        }


    };
}