

using System.Collections.Concurrent;
using System.Text;
using Game.Network;

namespace Game.Server
{


    public class GameQuery
    {
        public readonly ConnId connId;
        public readonly byte[] Raw;
        public readonly long ExpireTimeMs;
        public Action<QueryTaskResult> CallBack;

        public GameQuery(ConnId id, byte[] raw, long expireTimeMs, Action<QueryTaskResult> callBack)
        {
            connId = id;
            Raw = raw;
            ExpireTimeMs = expireTimeMs;
            CallBack = callBack;    
        }
    }

    public class GameMessage
    {
        public readonly ConnId connId;
        public readonly byte[] Raw;

        public GameMessage(ConnId id, byte[] raw) {connId = id; Raw = raw;}
    }

    public class GameSessionHandler : INetEventHandler
    {
        public int HandlerId => NetEventHandlerId.Constant.GameMessage;

        // Read in Race Cond
        private ConcurrentDictionary<SessionPlayerId, ConnId> _player_connectionDict; // (PlayerName, ConnectoinId)

        // Write in Race Cond
        private ConcurrentQueue<GameQuery> _queryQueue; 
        private ConcurrentQueue<GameMessage> _messageQueue;


        // Write & Read in Server Tick
        private INetAPI _net;
        private int _maxProcessPerTick = 30; // TODO: 이거 다른 값으로 변경. 일단 테스트용
        private bool _isGameRunning = false;



        public void QueryPlayer(SessionPlayerId playerId, byte[] raw, long expireTimeMs, Action<QueryTaskResult> callBack)
        {
            if (_player_connectionDict.TryGetValue(playerId, out var connId))
            {
                var req = new GameQuery(connId, raw, expireTimeMs, callBack);
                _queryQueue.Enqueue(req);
                return;
            }
            else return;
        }

        public void BroadCastPlayer(byte[] raw)
        {
            foreach (var connId in _player_connectionDict.Values) 
                _messageQueue.Enqueue(new GameMessage(connId, raw));
        }

        public void SendPlayer(SessionPlayerId playerId, byte[] raw) 
        {
            if (_player_connectionDict.TryGetValue(playerId, out var connId))
                _messageQueue.Enqueue(new GameMessage(connId, raw));
        }

        public GameSessionHandler(INetAPI net, string sessionOwner)
        {
            _player_connectionDict = new();
            _queryQueue = new();
            _messageQueue = new();
            _net = net;
        }

        public void Tick()
        {
            for (int i = 0; i < _maxProcessPerTick; i++)
            {
                if (!_queryQueue.TryDequeue(out var query)) break;

                _net.AsyncRequestQuery(
                    HandlerId, 
                    query.connId, 
                    query.Raw, 
                    query.ExpireTimeMs,
                    (connId, result) => {query.CallBack(result);}
                    );
            }

            for (int i = 0; i < _maxProcessPerTick; i++)
            {
                if (!_messageQueue.TryDequeue(out var message)) break;
                
                _net.Send(HandlerId, 0, message.connId, message.Raw); 
            }
        }

        private void StartGame()
        {
            var playerList = _player_connectionDict.Keys.ToArray();

            if (playerList.Count() != 2) 
                Log.WriteLog("Wrong Player Count. Wrong StartGame()");   
        }



        // Data
        public void OnReceive(ConnId connId, byte[] raw) { }
        public void OnRespond(ConnId connId, int queryNum, byte[] raw) { }
        public void OnQuery(ConnId connId, int queryNum, byte[] raw) {}

        // Control
        public void OnException(ConnId connId, byte[] raw, string msg) { }
        public void OnHello(ConnId connId, byte[] raw)
        {
            if (_player_connectionDict.Count >= 2) return;
            _ = _net.AsyncRequestQuery(HandlerId, connId, Encoding.UTF8.GetBytes("HELLO"), 3000, 
                (rspConnId, rsp) => // Succ Action
                {
                    var newId = SessionPlayerId.NewId();
                    _player_connectionDict[newId] = rspConnId;
                    Log.WriteLog($"Player Enter: [{newId}] From [{rspConnId}]");
                    if (_player_connectionDict.Count == 2 && !_isGameRunning)
                    {
                        _isGameRunning = true;
                        StartGame();
                    }
                }
                );
        }
        public void OnDisconnect(ConnId connId, byte[] raw) { }


    };
}