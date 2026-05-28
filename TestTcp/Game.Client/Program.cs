using System.Diagnostics;
using System.Text;
using Game.Network;

namespace Game.Client
{
    // ─── 테스트 파라미터 (런타임에 프리셋으로 채워짐) ─────────────────────
    class TestConfig
    {
        public int    TickTimeMs       = 4;
        public string ServerIp         = "127.0.0.1";
        public int    ServerPort       = 9000;
        public int    ConnectTimeoutMs = 5000;
        public int    ClientCount;
        public int    MsgPerClient;
        public int    MsgSizeBytes;
        public int    MsgIntervalMs    = 10;
        public int    QueryTimeoutMs   = 3000;

        // ── 프리셋 ────────────────────────────────────────────────────
        // 프리셋 1: 64클라 × 2.5KB × 200회
        public static TestConfig Preset1() => new()
        {
            ClientCount  = 64,
            MsgPerClient = 200,
            MsgSizeBytes = 2500,
        };

        // 프리셋 2: 2클라 × 2.5KB × 500회
        public static TestConfig Preset2() => new()
        {
            ClientCount  = 2,
            MsgPerClient = 500,
            MsgSizeBytes = 2500,
            TickTimeMs   = 15,
        };

        public string Describe() =>
            $"{ClientCount} clients × {MsgSizeBytes}B × {MsgPerClient} msgs  (interval={MsgIntervalMs}ms)";
    }

    // ─── 테스트 메세지 핸들러 ID ──────────────────────────────────────────
    static class HandlerId
    {
        public const int Echo = 100;
    }

    // ─── 간단한 바이트 배열 코덱 ──────────────────────────────────────────
    class RawBytesCodec : IPacketCodec<byte[]>
    {
        public static readonly RawBytesCodec Instance = new();
        public int GetSize(byte[] data) => data.Length;
        public void Write(ref PacketWriter writer, byte[] data) => writer.WriteBytes(data);
        public byte[] Read(ref PacketReader reader) => reader.ReadBytes(reader.Remain).ToArray();
    }

    // ─── 서버 측 에코 핸들러 ─────────────────────────────────────────────
    class EchoHandler : INetEventHandler
    {
        private readonly INetAPI _net;
        public int HandlerId => Game.Client.HandlerId.Echo;

        public EchoHandler(INetAPI net) => _net = net;

        public void OnHello(ConnId connId, byte[] raw)
            => Log.WriteLog($"[Server] Client connected: {connId}");

        public void OnDisconnect(ConnId connId, byte[] raw)
            => Log.WriteLog($"[Server] Client disconnected: {connId}");

        public void OnReceive(ConnId connId, byte[] raw)
            => Log.WriteLog($"[Server] Recv from {connId}");

        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
            => _net.SendRespond(HandlerId, queryNum, connId, raw, RawBytesCodec.Instance);

        public void OnRespond(ConnId connId, int queryNum, byte[] raw) { }
        public void OnException(ConnId connId, byte[] raw, string msg)
            => Log.WriteLog($"[Server] Exception from {connId}: {msg}");
    }

    // ─── 클라이언트 측 응답 핸들러 ───────────────────────────────────────
    class ClientEchoHandler : INetEventHandler
    {
        private readonly int _clientIndex;
        public int HandlerId => Game.Client.HandlerId.Echo;

        public ClientEchoHandler(int idx) => _clientIndex = idx;

        public void OnHello(ConnId connId, byte[] raw)
            => Log.WriteLog($"[Client#{_clientIndex}] Connected: {connId}");

        public void OnDisconnect(ConnId connId, byte[] raw)
            => Log.WriteLog($"[Client#{_clientIndex}] Disconnected");

        public void OnReceive(ConnId connId, byte[] raw) { }
        public void OnQuery(ConnId connId, int queryNum, byte[] raw) { }
        public void OnRespond(ConnId connId, int queryNum, byte[] raw) { }
        public void OnException(ConnId connId, byte[] raw, string msg)
            => Log.WriteLog($"[Client#{_clientIndex}] Exception: {msg}");
    }

    // ─── 통계 ─────────────────────────────────────────────────────────────
    class TestStats
    {
        private const int FrameOverhead = 20; // 4B length prefix + 16B codec header

        private int  _sent, _responded, _timedOut, _cancelled;
        private long _minRttMs = long.MaxValue;
        private long _maxRttMs = long.MinValue;
        private long _totalRttMs;

        public void RecordSent()      => Interlocked.Increment(ref _sent);
        public void RecordTimedOut()  => Interlocked.Increment(ref _timedOut);
        public void RecordCancelled() => Interlocked.Increment(ref _cancelled);

        public void RecordResponded(long rttMs)
        {
            Interlocked.Increment(ref _responded);
            Interlocked.Add(ref _totalRttMs, rttMs);

            long prev;
            do { prev = Volatile.Read(ref _minRttMs); } while (rttMs < prev && Interlocked.CompareExchange(ref _minRttMs, rttMs, prev) != prev);
            do { prev = Volatile.Read(ref _maxRttMs); } while (rttMs > prev && Interlocked.CompareExchange(ref _maxRttMs, rttMs, prev) != prev);
        }

        public void PrintSummary(TestConfig cfg)
        {
            int    sent      = _sent;
            int    responded = _responded;
            int    timedOut  = _timedOut;
            int    cancelled = _cancelled;
            double rate      = sent > 0 ? responded * 100.0 / sent : 0;

            int  netPacketBytes = FrameOverhead + cfg.MsgSizeBytes;
            long totalBytes     = (long)responded * netPacketBytes * 2;

            long minRtt = responded > 0 ? _minRttMs : 0;
            long maxRtt = responded > 0 ? _maxRttMs : 0;
            long avgRtt = responded > 0 ? _totalRttMs / responded : 0;

            Console.WriteLine();
            Console.WriteLine("┌─────────────────────────────────────────────────────┐");
            Console.WriteLine("│                  Test Result Summary                │");
            Console.WriteLine("├─────────────────────────────────────────────────────┤");
            Console.WriteLine($"│  Clients          : {cfg.ClientCount,-32}│");
            Console.WriteLine($"│  Msgs/client      : {cfg.MsgPerClient,-32}│");
            Console.WriteLine($"│  Payload size     : {cfg.MsgSizeBytes,5} B  (net frame: {netPacketBytes} B)        │");
            Console.WriteLine($"│  Send interval    : {cfg.MsgIntervalMs,5} ms                           │");
            Console.WriteLine($"│  Tick period      : {cfg.TickTimeMs,5} ms                           │");
            Console.WriteLine("├─────────────────────────────────────────────────────┤");
            Console.WriteLine($"│  Sent             : {sent,-32}│");
            Console.WriteLine($"│  Responded        : {responded,-32}│");
            Console.WriteLine($"│  TimedOut         : {timedOut,-32}│");
            Console.WriteLine($"│  Cancelled        : {cancelled,-32}│");
            Console.WriteLine($"│  Success rate     : {rate,6:F1} %                          │");
            Console.WriteLine("├─────────────────────────────────────────────────────┤");
            Console.WriteLine($"│  RTT min          : {minRtt,5} ms                           │");
            Console.WriteLine($"│  RTT max          : {maxRtt,5} ms                           │");
            Console.WriteLine($"│  RTT avg          : {avgRtt,5} ms                           │");
            Console.WriteLine($"│  Total net bytes  : {totalBytes,10} B (req+rsp, responded)  │");
            Console.WriteLine("└─────────────────────────────────────────────────────┘");
        }
    }

    class Program
    {
        static async Task Main()
        {
            Log.SetLogger(Console.WriteLine);

            Console.WriteLine("Mode?");
            Console.WriteLine("  s  : server");
            Console.WriteLine("  c  : client (remote)");
            Console.WriteLine("  t1 : local test — 64 clients × 2.5KB × 200 msgs");
            Console.WriteLine("  t2 : local test —  2 clients × 2.5KB × 500 msgs");
            Console.Write("> ");
            var mode = Console.ReadLine()?.Trim().ToLowerInvariant() ?? "t1";

            if (mode == "s")
                await RunServer();
            else if (mode == "c")
                await RunClients(SelectPreset());
            else if (mode == "t2")
                await RunLocalTest(TestConfig.Preset2());
            else
                await RunLocalTest(TestConfig.Preset1());
        }

        // ── 원격 클라이언트 모드에서 프리셋 선택 ─────────────────────────
        static TestConfig SelectPreset()
        {
            Console.WriteLine("Preset?");
            Console.WriteLine("  1 : 64 clients × 2.5KB × 200 msgs");
            Console.WriteLine("  2 :  2 clients × 2.5KB × 500 msgs");
            Console.Write("> ");
            var choice = Console.ReadLine()?.Trim() ?? "1";
            return choice == "2" ? TestConfig.Preset2() : TestConfig.Preset1();
        }

        // ══════════════════════════════════════════════════════════════════
        //  서버 모드
        // ══════════════════════════════════════════════════════════════════
        static async Task RunServer()
        {
            var cfg = new TestConfig();
            var net = NetworkManager.CreateNetworkManager(cfg.ServerPort, 10);
            net.SetReceiveHandler(new EchoHandler(net));
            net.SetControlHandler(new EchoHandler(net));
            net.Start();

            Console.WriteLine($"[Server] Listening on port {cfg.ServerPort}. Press 'q' to quit.");

            var cts = new CancellationTokenSource();
            _ = Task.Run(() =>
            {
                while (Console.ReadLine()?.Trim().ToLowerInvariant() != "q") { }
                cts.Cancel();
            });

            await TickLoop(net, cts.Token);
            await net.StopAsync();
            Console.WriteLine("[Server] Stopped.");
        }

        // ══════════════════════════════════════════════════════════════════
        //  클라이언트 모드 (원격 서버 접속)
        // ══════════════════════════════════════════════════════════════════
        static async Task RunClients(TestConfig cfg)
        {
            Console.WriteLine($"[Client] {cfg.Describe()} → {cfg.ServerIp}:{cfg.ServerPort}");

            var stats = new TestStats();
            var tasks = new List<Task>();
            for (int i = 0; i < cfg.ClientCount; i++)
                tasks.Add(RunSingleClient(i, cfg, stats));

            await Task.WhenAll(tasks);
            stats.PrintSummary(cfg);
        }

        // ══════════════════════════════════════════════════════════════════
        //  로컬 자동 테스트 (서버 + 클라이언트 동일 프로세스)
        // ══════════════════════════════════════════════════════════════════
        static async Task RunLocalTest(TestConfig cfg)
        {
            Console.WriteLine($"[Test] {cfg.Describe()}");

            var serverNet = NetworkManager.CreateNetworkManager(cfg.ServerPort, 10);
            serverNet.SetReceiveHandler(new EchoHandler(serverNet));
            serverNet.SetControlHandler(new EchoHandler(serverNet));
            serverNet.Start();

            var cts        = new CancellationTokenSource();
            var serverTick = Task.Run(async () =>
            {
                var sw = new Stopwatch();
                while (!cts.IsCancellationRequested)
                {
                    sw.Restart();
                    serverNet.Tick();
                    sw.Stop();
                    int sleep = cfg.TickTimeMs - (int)sw.ElapsedMilliseconds;
                    if (sleep > 0) await Task.Delay(sleep);
                }
            });

            await Task.Delay(200);

            var stats       = new TestStats();
            var clientTasks = new List<Task>();
            for (int i = 0; i < cfg.ClientCount; i++)
                clientTasks.Add(RunSingleClient(i, cfg, stats));

            await Task.WhenAll(clientTasks);

            cts.Cancel();
            await serverTick;
            await serverNet.StopAsync();

            stats.PrintSummary(cfg);
            Console.WriteLine("[Test] Done.");
        }

        // ──────────────────────────────────────────────────────────────────
        //  단일 클라이언트 실행
        // ──────────────────────────────────────────────────────────────────
        static async Task RunSingleClient(int idx, TestConfig cfg, TestStats stats)
        {
            var net     = NetworkManager.CreateNetworkManager(0, 10);
            var handler = new ClientEchoHandler(idx);
            net.SetReceiveHandler(handler);
            net.SetControlHandler(handler);
            net.Start();

            var cts    = new CancellationTokenSource();
            var tickSw = new Stopwatch();

            var tickTask = Task.Run(async () =>
            {
                while (!cts.IsCancellationRequested)
                {
                    tickSw.Restart();
                    net.Tick();
                    tickSw.Stop();
                    int sleep = cfg.TickTimeMs - (int)tickSw.ElapsedMilliseconds;
                    if (sleep > 0) await Task.Delay(sleep);
                }
            });

            try
            {
                var connId = await net.ConnectTo(cfg.ServerIp, cfg.ServerPort, cfg.ConnectTimeoutMs);
                if (connId is null)
                {
                    Log.WriteLog($"[Client#{idx}] Connection failed.");
                    return;
                }

                var payload = BuildPayload(idx, cfg.MsgSizeBytes);
                int sent    = 0;
                var sendSw  = new Stopwatch();

                while (cfg.MsgPerClient == 0 || sent < cfg.MsgPerClient)
                {
                    if (cfg.MsgIntervalMs > 0)
                        await Task.Delay(cfg.MsgIntervalMs);

                    if (!net.IsConnValid(connId)) break;

                    sendSw.Restart();
                    var result = await net.AsyncSendQuery(
                        HandlerId.Echo, connId,
                        payload, RawBytesCodec.Instance,
                        cfg.QueryTimeoutMs);
                    sendSw.Stop();

                    stats.RecordSent();
                    sent++;

                    if (result.IsResponded)
                    {
                        stats.RecordResponded(sendSw.ElapsedMilliseconds);
                        Log.WriteLog($"[Client#{idx}] Query#{sent} OK  rtt~{sendSw.ElapsedMilliseconds}ms");
                    }
                    else if (result.IsTimeOut)
                    {
                        stats.RecordTimedOut();
                        Log.WriteLog($"[Client#{idx}] Query#{sent} TIMEOUT");
                    }
                    else
                    {
                        stats.RecordCancelled();
                        Log.WriteLog($"[Client#{idx}] Query#{sent} CANCELLED");
                    }
                }
            }
            finally
            {
                cts.Cancel();
                await tickTask;
                await net.StopAsync();
                Log.WriteLog($"[Client#{idx}] Done.");
            }
        }

        // ──────────────────────────────────────────────────────────────────
        //  공통 틱 루프 (서버 단독 모드용)
        // ──────────────────────────────────────────────────────────────────
        static async Task TickLoop(NetworkManager net, CancellationToken ct)
        {
            var sw = new Stopwatch();
            while (!ct.IsCancellationRequested)
            {
                sw.Restart();
                net.Tick();
                sw.Stop();
                int sleep = new TestConfig().TickTimeMs - (int)sw.ElapsedMilliseconds;
                if (sleep > 0) await Task.Delay(sleep, ct).ConfigureAwait(false);
            }
        }

        // ──────────────────────────────────────────────────────────────────
        //  페이로드 생성
        // ──────────────────────────────────────────────────────────────────
        static byte[] BuildPayload(int clientIdx, int size)
        {
            var header = Encoding.UTF8.GetBytes($"C{clientIdx}:");
            var buf    = new byte[Math.Max(size, header.Length)];
            header.CopyTo(buf, 0);
            for (int i = header.Length; i < buf.Length; i++)
                buf[i] = (byte)('A' + (i % 26));
            return buf;
        }
    }
}
