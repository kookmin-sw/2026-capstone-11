using Game.Network;
using Game.Network.Protocol;

namespace Game.Server
{
    public class ServiceHandler : INetEventHandler
    {

        public const int Id = 444;
        private INetAPI _net;
        private IAuthenticator _auth;
        private ServiceContext _context;


        public ServiceHandler(INetAPI net, IAuthenticator authenticator, ServiceContext context)
        {
            _net = net;
            _auth = authenticator;
            _context = context;
        }

        // Data
        public void OnReceive(string ConnId, byte[] raw){}
        public void OnRespond(string ConnId, int queryNum, byte[] raw)
        {
            var connInfo = ConnectionInfo.Deserialize(raw);
            if (connInfo == null)
            {
                Log.WriteLog("[Session]: Hello Packet Failure");
                _net.Disconnect(ConnId);
                return;
            }

            var authInfo = _auth.Authenticate(ConnId, connInfo);

            if (!authInfo.IsAuth)
            {
                Log.WriteLog($"[Session]: Authenticate Fail. Reason: {authInfo.FailMsg}");
                _net.Disconnect(ConnId);
                return;
            }

            var pingInfo = new PingInfo(_context.Opt.pingFailCountToDisconnect);

            _context.Add(ConnId, connInfo, pingInfo, authInfo);

            Log.WriteLog($"[Session] : New Player Entered \n"
                + "\tConnId=" + ConnId
                + "\n\tAccountName=" + connInfo.accountName
                + "\n\taccountId="   + connInfo.accountId
                + "\n\tappVersion="  + connInfo.appVersion
                + "\n\tsessionId="   + connInfo.sessionId
                + "\n\ttoken="       + connInfo.token
            );
        }

        public void OnQuery(string ConnId, int queryNum, byte[] raw)
            => _net.Send(Id, queryNum, ConnId, ConnectionInfo.Serialize(_context.SelfInfo));

        // Control
        public void OnException(string ConnId, byte[] raw, string msg) { /*System Handler will control exception by publishing Disconnect Out Event*/}
        public void OnHello(string ConnId, byte[] raw)
        {
            if (_context.InfoDictionary.Count() >= _context.Opt.maxConnPerService) return;

            _ = _net.AsyncRequestQuery(Id, ConnId, ConnectionInfo.Serialize(_context.SelfInfo), _context.Opt.helloTimeOutMs,
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
            => _context.Remove(ConnId);


    };
}