using System.Collections.Concurrent;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;

namespace Game.Network
{
    public class NetConnectionManager
    {
        private TcpListener _listener;
        private Task? _acceptLoopTask;
        private CancellationTokenSource? _cts;
        private ConcurrentDictionary<string, Connection> _connectionDict;
        private int _maxControlPerTick;
        private int _maxDataPerTick;



        public NetConnectionManager(int portNum, int maxControlPerTick, int maxDataPerTick)
        {
            _listener = new TcpListener(IPAddress.Any, portNum);
            _acceptLoopTask = null;
            _cts = null;
            _connectionDict = new ConcurrentDictionary<string, Connection>();
            _maxControlPerTick = maxControlPerTick;
            _maxDataPerTick = maxDataPerTick;
        }

        public void Init(NetEventQueue q)
        {
            if (_cts != null)
            {
                Log.WriteLog("NetConnectionManger is already running.");
                return;
            }

            _cts = new CancellationTokenSource();
            try
            {
                _listener.Start();
                _acceptLoopTask = AsyncAcceptLoop(_cts.Token, q);

            }
            catch (SocketException se)
            {
                Log.WriteLog($"SocketException: {se.Message}");
                _cts = null;
            }
            catch (Exception e)
            {
                Log.WriteLog($"Exception : {e.Message}");
                _cts = null;
            }

            return;
        }

        public void Tick(NetEventQueue q)
        {
            for (int i = 0; i < _maxControlPerTick; i++)
            {
                if (!q.OutControlQueue.TryDequeue(out var outCon)) break;

                switch (outCon.type)
                {
                    case NetOutEventType.Disconnect:
                        if (_connectionDict.TryRemove(outCon.ConnId, out var deleted))
                            _ = deleted.AsyncEndConnection();
                        break;
                }
            }


            for (int i = 0; i < _maxDataPerTick; i++)
            {
                if (!q.OutQueue.TryDequeue(out var outEv)) break;

                switch (outEv.type)
                {
                    case NetOutEventType.Send:
                        if (_connectionDict.TryGetValue(outEv.ConnId, out var conn))
                            conn.TrySend(outEv.data);
                        break;

                    case NetOutEventType.BroadCast:
                        foreach (var connEach in _connectionDict.Values)
                        {
                            connEach.TrySend(outEv.data);
                        }
                        break;
                }
            }
        }

        public async Task Stop()
        {
            if (_cts == null) return;

            _cts.Cancel();
            _listener.Stop();

            try
            {
                if (_acceptLoopTask != null) await _acceptLoopTask;
            }
            catch (Exception e)
            {
                Log.WriteLog($"서버 중단 중 에러 {e.Message}");
            }

            _cts.Dispose();
            _cts = null;
            _acceptLoopTask = null;

            foreach (var item in _connectionDict)
            {
                await item.Value.AsyncEndConnection();
            }
        }

        public string GetState()
        {
            string dictState = "";

            foreach (var connect in _connectionDict.Values)
            {
                dictState += "\t" + connect.GetConnectionId() + " | " + connect.GetRemoteEndPoint() + "\n";
            }

            return $"[ConnectionManager:{this}]\n" +
                    $"\tNow Connectied: {_connectionDict.Count}\n" +
                    dictState
                    ;
        }

        public bool TryGetConnIdList(int minConnCount, out List<string> connIds)
        {
            connIds = new();

            if (minConnCount > _connectionDict.Count)
                return false;

            foreach (var item in _connectionDict)
                connIds.Add(item.Key);

            return true;
        }

        public bool IsConnValid(string connId) => _connectionDict.ContainsKey(connId);


        public async Task<string?> ConnectTo(string ipAddr, int portNum, NetEventQueue q, int expireTimeMs)
        {
            if (_cts == null || _cts.IsCancellationRequested) return null;

            var conn = await Connection.ListenAndCreateConnection(ipAddr, portNum, q, expireTimeMs);

            if (conn != null && _connectionDict.TryAdd(conn.GetConnectionId(), conn))
            { 
                conn.Start(); 
                return conn.GetConnectionId(); 
            }

            return null;
        }

        private async Task AsyncAcceptLoop(CancellationToken ct, NetEventQueue q)
        {
            try
            {
                while (!ct.IsCancellationRequested)
                {
                    var client = await _listener.AcceptTcpClientAsync().ConfigureAwait(false);

                    // TODO: 유니티면 아래 사용
                    //var client = await _listener.AcceptTcpClientAsync().ConfigureAwait(false);


                    Log.WriteLog("서버 클라이언트 연결 성공");
                    Log.WriteLog($"[Client EP] : {client.Client.RemoteEndPoint}");
                    Log.WriteLog($"[Server EP] : {client.Client.LocalEndPoint}");

                    _ = HandleAcceptedClient(client, q);
                }
            }
            catch (SocketException se)
            {
                Log.WriteLog($"AcceptLoop Fail : {se.Message}");
            }
            catch (Exception e) { Log.WriteLog(e.Message); }
        }

        private async Task HandleAcceptedClient(TcpClient client, NetEventQueue q)
        {
            var conn = Connection.CreateConnection(client, q);

            if (!_connectionDict.TryAdd(conn.GetConnectionId(), conn))
            {
                Log.WriteLog("ConnectionDict Fail");
                await conn.AsyncEndConnection();
            }
            else conn.Start();
        }
    }
}