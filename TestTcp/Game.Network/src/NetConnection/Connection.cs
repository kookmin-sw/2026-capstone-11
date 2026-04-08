
using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Drawing;
using System.IO.Compression;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;


namespace Game.Network
{

    public class Connection
    {
        private readonly TcpClient _client;
        private readonly NetworkStream _stream;
        private readonly ConcurrentQueue<byte[]> _channel;
        private readonly NetEventQueue _queue;

        private CancellationTokenSource? _cts;
        private SemaphoreSlim _hasSomethingToSend = new(0);
        private Task? _sendLoopTask;
        private Task? _receiveLoopTask;
        private int _started = 0;

        private ConnId _id;
        private bool _isConnected;

        public ConnId GetConnectionId() => _id;
        public string? GetRemoteEndPoint() => _client.Client.RemoteEndPoint?.ToString();


        public static Connection CreateConnection(TcpClient tcpClient, NetEventQueue q)
        {
            Connection conn = new Connection(tcpClient, q);
            return conn;
        }

        public void Start()
        {
            // 중복 호출 가드.  
            if (Interlocked.Exchange(ref _started, 1) == 1) return;

            _cts = new CancellationTokenSource();
            _sendLoopTask = AsyncSendLoop(_cts.Token);
            _receiveLoopTask = AsyncReceiveLoop(_cts.Token);
            _queue.InControlQueue.Enqueue(NetInEvent.Hello(
                _id,
                Array.Empty<byte>()
            ));
        }

        public static async Task<Connection?> ListenAndCreateConnection(string ip, int portNum, NetEventQueue q, int expireTimeMs)
        {
            TcpClient? tcp = null;
            Task? connTask = null;
            
            try
            {
                tcp = new TcpClient();
                connTask = tcp.ConnectAsync(ip, portNum);

                var done = await Task.WhenAny(connTask, Task.Delay(expireTimeMs));
                if (done != connTask) 
                { 
                    try { tcp.Close(); } catch {}
                    throw new TimeoutException();
                }
                
                await connTask;
                return new Connection(tcp, q);
            }
            catch (Exception e)
            {
                try { tcp?.Close(); } catch {}
                try {if (connTask != null) await connTask;} catch {}

                q.InControlQueue.Enqueue(NetInEvent.Exception(ConnId.Default(), Array.Empty<byte>(), $"Fail To Connect. Exception MSG: {e.Message}"));
                return null;
            }
        }

        public static async Task<Connection?> ListenAndCreateConnection(string ip, int portNum, ConnId connId, NetEventQueue q, int expireTimeMs)
        {
            TcpClient? tcp = null;
            Task? connTask = null;
            
            try
            {
                tcp = new TcpClient();
                connTask = tcp.ConnectAsync(ip, portNum);

                var done = await Task.WhenAny(connTask, Task.Delay(expireTimeMs));
                if (done != connTask) 
                { 
                    try { tcp.Close(); } catch {}
                    throw new TimeoutException();
                }
                
                await connTask;
                return new Connection(tcp, q, connId);
            }
            catch (Exception e)
            {
                try { tcp?.Close(); } catch {}
                try {if (connTask != null) await connTask;} catch {}

                q.InControlQueue.Enqueue(NetInEvent.Exception(ConnId.Default(), Array.Empty<byte>(), $"Fail To Connect. Exception MSG: {e.Message}"));
                return null;
            }
        }

        public bool TrySend(byte[] data)
        {
            if (_isConnected == false || _cts == null || _cts.IsCancellationRequested == true) return false;

            _channel.Enqueue(data);
            _hasSomethingToSend.Release();
            return true;
        }


        private Connection(TcpClient tcpClient, NetEventQueue q)
        {
            _client = tcpClient;
            _stream = tcpClient.GetStream();
            _channel = new ConcurrentQueue<byte[]>();

            _queue = q;
            _isConnected = true;

            _id = ConnId.Get();
        }

        private Connection(TcpClient tcpClient, NetEventQueue q, ConnId connId)
        {
            _client = tcpClient;
            _stream = tcpClient.GetStream();
            _channel = new ConcurrentQueue<byte[]>();

            _queue = q;
            _isConnected = true;

            _id = connId;
        }

        private async Task AsyncSendLoop(CancellationToken token)
        {
            try
            {
                while (!token.IsCancellationRequested)
                {
                    await _hasSomethingToSend.WaitAsync(token);

                    while (_channel.TryDequeue(out var data))
                    {
                        byte[] size = BitConverter.GetBytes(data.Length);
                        await _stream.WriteAsync(size, 0, size.Length, token);
                        await _stream.WriteAsync(data, 0, data.Length, token);
                    }

                }
            }
            catch (OperationCanceledException) when (token.IsCancellationRequested)
            {
                // don't catch this exception
            }
            catch (Exception e)
            {
                _queue.InControlQueue.Enqueue(NetInEvent.Exception(
                    GetConnectionId(),
                    Array.Empty<byte>(),
                    $"{e.Message}"
                ));
            }

        }
        private async Task AsyncReceiveLoop(CancellationToken token)
        {
            byte[] sizeBuffer = new byte[4];
            try
            {
                while (!token.IsCancellationRequested)
                {

                    int n = await _stream.ReadAsync(sizeBuffer, 0, sizeBuffer.Length, token);
                    if (n == 0) throw new SocketException();

                    int size = BitConverter.ToInt32(sizeBuffer);
                    byte[] dataBuffer = new byte[size];

                    n = await _stream.ReadAsync(dataBuffer, 0, dataBuffer.Length, token);
                    if (n == 0) throw new SocketException();

                    _queue.InQueue.Enqueue(NetInEvent.Receive(
                        GetConnectionId(),
                        dataBuffer,
                        "Data Received"
                    ));
                }

            }
            catch (OperationCanceledException) when (token.IsCancellationRequested)
            {
                // don't catch this exception
            }
            catch (Exception e)
            {
                _queue.InControlQueue.Enqueue(NetInEvent.Exception(
                    GetConnectionId(),
                    Array.Empty<byte>(),
                    $"{e.Message}"
                ));
            }
        }

        public async Task AsyncEndConnection()
        {
            _cts?.Cancel();
            _client.Close();

            if (_sendLoopTask != null) await _sendLoopTask;
            if (_receiveLoopTask != null) await _receiveLoopTask;

            _cts = null;
            _isConnected = false;
            _queue.InControlQueue.Enqueue(NetInEvent.Disconnect(
                GetConnectionId(),
                Array.Empty<byte>()
            ));
        }
    }
}