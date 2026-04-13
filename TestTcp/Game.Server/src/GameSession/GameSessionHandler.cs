

using System.Collections.Concurrent;
using System.ComponentModel;
using System.Reflection.Metadata.Ecma335;
using System.Runtime.CompilerServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Serialization.Metadata;
using Microsoft.VisualBasic;
using Game.Network;

namespace Game.Server
{


    public class GameQuery
    {
        public readonly string ConnId;
        public readonly byte[] Raw;
        public readonly long ExpireTimeMs;
        public TaskCompletionSource<QueryTaskResult> tcs;

        public GameQuery(string playerName, byte[] raw, long expireTimeMs)
        {
            ConnId = playerName;
            Raw = raw;
            ExpireTimeMs = expireTimeMs;
            tcs = new();
        }
    }

    public class GameMessage
    {
        public readonly string ConnId;
        public readonly byte[] Raw;

        public GameMessage(string connId, byte[] raw) {ConnId = connId; Raw = raw;}
    }

    public class GameSessionHandler : INetEventHandler
    {
        private const int Id = 444;

        // Read in Race Cond
        private ConcurrentDictionary<string, string> _player_connectionDict; // (PlayerName, ConnectoinId)

        // Write in Race Cond
        private ConcurrentQueue<GameQuery> _queryQueue; 
        private ConcurrentQueue<GameMessage> _messageQueue;


        // Write & Read in Server Tick
        private INetAPI _net;
        private string _sessionOwner;
        private int _maxProcessPerTick = 30; // TODO: 이거 다른 값으로 변경. 일단 테스트용
        private bool _isGameRunning = false;



        public async Task<QueryTaskResult> AsyncQueryPlayer(string playerName, byte[] raw, long expireTimeMs)
        {
            if (_player_connectionDict.TryGetValue(playerName, out var connId))
            {
                var req = new GameQuery(connId, raw, expireTimeMs);
                _queryQueue.Enqueue(req);
                return await req.tcs.Task;
            }
            else return QueryTaskResult.CancelledResult;
        }

        public void BroadCastPlayer(byte[] raw)
        {
            foreach (var connId in _player_connectionDict.Values) 
                _messageQueue.Enqueue(new GameMessage(connId, raw));
        }

        public void SendPlayer(string playerName, byte[] raw) 
        {
            if (_player_connectionDict.TryGetValue(playerName, out var connId))
                _messageQueue.Enqueue(new GameMessage(connId, raw));
        }



        public GameSessionHandler(INetAPI net, string sessionOwner)
        {
            _player_connectionDict = new();
            _queryQueue = new();
            _messageQueue = new();
            _net = net;
            _sessionOwner = sessionOwner;
        }

        public void Tick()
        {
            for (int i = 0; i < _maxProcessPerTick; i++)
            {
                if (!_queryQueue.TryDequeue(out var query)) break;

                _net.AsyncRequestQuery(
                    Id, 
                    query.ConnId, 
                    query.Raw, 
                    query.ExpireTimeMs,
                    query.tcs
                    );
            }

            for (int i = 0; i < _maxProcessPerTick; i++)
            {
                if (!_messageQueue.TryDequeue(out var message)) break;
                
                _net.Send(Id, 0, message.ConnId, message.Raw); 
            }
        }

        private void StartGame()
        {
            RockScissorsPaperGameContext context = new();
            var playerList = _player_connectionDict.Keys.ToArray();

            if (playerList.Count() != 2) 
                Log.WriteLog("Wrong Player Count. Wrong StartGame()");   

            context.player_1 = playerList[0];
            context.player_2 = playerList[1];
            context.session = this;

            var game = new RockScissorsPaperGame(context);
            Task.Run(game.RunGame);
        }



        // Data
        public void OnReceive(string ConnId, byte[] raw) { }
        public void OnRespond(string ConnId, int queryNum, byte[] raw) { }
        public void OnQuery(string ConnId, int queryNum, byte[] raw) {}

        // Control
        public void OnException(string ConnId, byte[] raw, string msg) { }
        public void OnHello(string ConnId, byte[] raw)
        {
            if (_player_connectionDict.Count >= 2) return;
            _ = _net.AsyncRequestQuery(Id, ConnId, Encoding.UTF8.GetBytes("HELLO"), 3000, 
                (answerRaw) => // Succ Action
                {
                    string playerName = Encoding.UTF8.GetString(answerRaw);
                    _player_connectionDict[playerName] = ConnId;
                    Log.WriteLog($"Player Enter: [{playerName}] From [{ConnId}]");
                    if (_player_connectionDict.Count == 2 && !_isGameRunning)
                    {
                        _isGameRunning = true;
                        StartGame();
                    }
                }, 
                () => // Fail Action
                {
                    Log.WriteLog($"Player Answer TimeOut. Target ConnectionID: [{ConnId}]");
                }
                );
        }
        public void OnDisconnect(string ConnId, byte[] raw) { }


    };
}