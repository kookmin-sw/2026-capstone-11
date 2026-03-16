using Game.Network;
using Game.Network.Protocol;

namespace Game.Server
{
    public class SessionHandler : INetEventHandler
    {

        public const int Id = 444;
        private INetAPI _net;
        private ConnectionInfo _selfConnectionInfo;
        private Dictionary<string, ConnectionInfo> _connectionInfoDict; // (ConnId, (Ping, ConnectoinInfo))
        private Dictionary<string, long> _pingDict;
        private int _pingInterval;
        private int _last;

        public SessionHandler(INetAPI net, ConnectionInfo selfConnInfo, int maxPlayerPerSession, int pingInterval)
        {
            _net = net;
            _selfConnectionInfo = selfConnInfo;
            _connectionInfoDict = new();
            _pingDict = new();
            _pingInterval = pingInterval;
            _last = 0;
        }

        public void Tick(int delta)
        {
            _last += delta;
            if (_last > _pingInterval)
            {
                _last = 0;

                Log.WriteLog("Ping!!");

                var now = GameTime.GetNow();
                foreach (var connId in _connectionInfoDict.Keys.ToArray())
                {
                    _ = _net.AsyncRequestQuery(Id, connId, Array.Empty<byte>(), 5000,
                        (answerRaw) =>
                        {
                            if (_connectionInfoDict.TryGetValue(connId, out var info))
                            {
                                _pingDict[connId] = GameTime.GetNow() - now;
                                Log.WriteLog($"[Session]: {info.accountName}-{connId}.Ping={_pingDict[connId]}");
                            }
                        }, 
                        () =>  
                        {
                            _connectionInfoDict.TryGetValue(connId, out var info);
                            _net.Disconnect(connId);
                            Log.WriteLog($"[Session]: {info.accountName}-{connId}.Ping Failed. Disconnect Event Publish");
                        }
                    );
                }

            }
        }

        // Data
        public void OnReceive(string ConnId, byte[] raw)
        {
            var info = ConnectionInfo.Deserialize(raw);
            if (info == null)
            {
                Log.WriteLog($"[Session] : Wrong Packet Received!");
                return;
            }

            Log.WriteLog($"[Session] : New Player Entered \n"
                + "\tConnId=" + ConnId 
                + "\n\tAccountName=" + info.Value.accountName
                + "\n\taccountId="+ info.Value.accountId
                + "\n\tappVersion="+ info.Value.appVersion
                + "\n\tsessionId="+ info.Value.sessionId
                + "\n\ttoken="+ info.Value.token  
            );
            _connectionInfoDict.Add(ConnId, info.Value);
            _pingDict.Add(ConnId, 0);
        }
        public void OnRespond(string ConnId, int queryNum, byte[] raw) {}

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
        {
            _net.Send(Id, queryNum, ConnId, Array.Empty<byte>());
        }


        // Control
        public void OnException(string ConnId, byte[] raw, string msg) {}
        public void OnHello(string ConnId, byte[] raw)
        {
            _net.Send(Id, 0, ConnId, ConnectionInfo.Serialize(_selfConnectionInfo)); 
            Log.WriteLog("[Session]: Send Hello Info");           
        }
        public void OnDisconnect(string ConnId, byte[] raw)
        {
            if (_connectionInfoDict.ContainsKey(ConnId)) 
            {
                _connectionInfoDict.Remove(ConnId);
                _pingDict.Remove(ConnId);
            }
        }


    };
}