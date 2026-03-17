using Game.Network;
using Game.Network.Protocol;

namespace Game.Server
{
    public class ServiceHandler : INetEventHandler
    {

        public const int Id = 444;
        private INetAPI _net;
        private IAuthenticator _auth;
        private ConnectionInfo _selfConnectionInfo;
        private ServiceContext _context;

        // Session Opt
        private int _playerPerSession;
        private int _helloQueryTimeOutMs;

        private int _last;

        public ServiceHandler(INetAPI net, IAuthenticator authenticator, ConnectionInfo selfConnInfo,
            int playerPerSession, int helloQueryTimeOutMs = 10000)
        {
            _net = net;
            _auth = authenticator;
            _selfConnectionInfo = selfConnInfo;
            

            _playerPerSession = playerPerSession;
            _helloQueryTimeOutMs = helloQueryTimeOutMs;

            _last = 0;
        }

        public void Tick(int deltaMs) {}

        // Data
        public void OnReceive(string ConnId, byte[] raw){}
        public void OnRespond(string ConnId, int queryNum, byte[] raw)
        {
            var info = ConnectionInfo.Deserialize(raw);
            if (info == null)
            {
                Log.WriteLog("[Session]: Hello Packet Failure");
                _net.Disconnect(ConnId);
                return;
            }

            var authResult = _auth.Authenticate(ConnId, info);

            if (!authResult.IsAuth)
            {
                Log.WriteLog($"[Session]: Authenticate Fail. Reason: {authResult.FailMsg}");
                _net.Disconnect(ConnId);
                return;
            }

            //_connectionInfoDict.Add(ConnId,info);

            Log.WriteLog($"[Session] : New Player Entered \n"
                + "\tConnId=" + ConnId
                + "\n\tAccountName=" + info.accountName
                + "\n\taccountId="   + info.accountId
                + "\n\tappVersion="  + info.appVersion
                + "\n\tsessionId="   + info.sessionId
                + "\n\ttoken="       + info.token
            );
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
            => _net.Send(Id, queryNum, ConnId, ConnectionInfo.Serialize(_selfConnectionInfo));

        // Control
        public void OnException(string ConnId, byte[] raw, string msg) { }
        public void OnHello(string ConnId, byte[] raw)
        {
            _ = _net.AsyncRequestQuery(Id, ConnId, ConnectionInfo.Serialize(_selfConnectionInfo), _helloQueryTimeOutMs,
                (answerRaw) => {},
                () => // TimeOutAction
                {
                    Log.WriteLog("[Session]: Authenticate Fail. Reason: Hello Time Out.");
                    _net.Disconnect(ConnId);
                }
                );

            Log.WriteLog("[Session]: Send Hello Info");
        }
        public void OnDisconnect(string ConnId, byte[] raw)
        {
            // if (_connectionInfoDict.ContainsKey(ConnId))
            //     _connectionInfoDict.Remove(ConnId);
        }


    };
}