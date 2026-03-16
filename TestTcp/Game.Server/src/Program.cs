using System.Diagnostics;
using System.IO.Pipelines;
using System.Net.Security;
using System.Threading.Tasks;
using Game.Network;
using Game.Network.Protocol;


namespace Game.Server
{
    class Program
    {
        public const int TickTime = 15;
        static async Task Main()
        {
            Log.SetLogger(Console.WriteLine);

            Console.WriteLine("Server mode : s, Client mode : c.. On New Project");
            var line = Console.ReadLine();
            if (line != null && line.Trim().Equals("s", StringComparison.OrdinalIgnoreCase))
            {
                var server = NetworkManager.CreateNetworkManager(TransferConfig.ServerPortNum, 10);
                //var PingPong = new PingPongHandler(server, 5000);
                //var Session = new GameSessionHandler(server, "Server"); 
                
                ConnectionInfo info = new ConnectionInfo(
                    NetworkType.Dedicated,
                    ConnectionType.Server,
                    1,
                    0,
                    "Server",
                    "Develop-0.0.0",
                    Guid.NewGuid().ToString()
                );

                var Sessionh = new SessionHandler(server, info, 2, 5000);
                
                //server.SetReceiveHandler(NetEventHandlerId.PingPong, PingPong);
                //server.SetControlHandler(PingPong);
                // server.SetReceiveHandler(444, Session);
                // server.SetControlHandler(Session);
                server.SetReceiveHandler(SessionHandler.Id, Sessionh);
                server.SetControlHandler(Sessionh);


                server.Start();


                Console.WriteLine("q를 입력해 서버 중단");

                var cts = new CancellationTokenSource();

                var inputTask = Task.Run(() =>
                {
                    while (true)
                    {
                        var line = Console.ReadLine();
                        if (line != null && line.Trim().Equals("q", StringComparison.OrdinalIgnoreCase))
                        {
                            cts.Cancel();
                            break;
                        }
                        else if (line != null && line.Trim().Equals("s", StringComparison.OrdinalIgnoreCase))
                        {
                            Log.WriteLog(server.GetNetState());
                        }
                    }
                });

                try
                {
                    var stopwatch = new Stopwatch();
                    long delta = 0;

                    Console.WriteLine("Server Running");

                    while (!cts.IsCancellationRequested)
                    {
                        stopwatch.Restart();

                        server.Tick();
                        // PingPong.Tick(TickTime);
                        // Session.Tick();
                        Sessionh.Tick(TickTime);

                        stopwatch.Stop();

                        delta = stopwatch.ElapsedMilliseconds;
                        int sleepTime = TickTime - (int)delta;
                        if (sleepTime > 0) Thread.Sleep(sleepTime);

                        else Log.WriteLog("TickTime over");
                    }
                }
                catch (OperationCanceledException)
                {

                }
                finally
                {
                    await server.StopAsync();
                    Console.WriteLine("Server stopped.");
                }


            }
            else if (line != null && line.Trim().Equals("c", StringComparison.OrdinalIgnoreCase))
            {
                var client = NetworkManager.CreateNetworkManager(0, 10);
                var PingPong = new PingPongHandler(client, 5000);
                client.SetReceiveHandler(NetEventHandlerId.PingPong, PingPong);
                client.SetControlHandler(PingPong);
                client.Start();
                await client.ConnectTo(
                    TransferConfig.ServerIPAddress,
                    TransferConfig.ServerPortNum,
                    3000
                    );

                Console.WriteLine("q를 입력해 클라이언트 중단. 문자를 넣어 전송");

                var cts = new CancellationTokenSource();

                var inputTask = Task.Run(() =>
                {
                     while (true)
                    {
                        var line = Console.ReadLine();
                        if (line != null && line.Trim().Equals("q", StringComparison.OrdinalIgnoreCase))
                        {
                            cts.Cancel();
                            break;
                        }
                        else if (line != null && line.Trim().Equals("s", StringComparison.OrdinalIgnoreCase))
                        {
                            Log.WriteLog(client.GetNetState());
                        }
                    }
                });

                try
                {
                    var stopwatch = new Stopwatch();
                    long delta = 0;

                    while (!cts.IsCancellationRequested)
                    {
                        stopwatch.Restart();

                        client.Tick();
                        //PingPong.Tick(TickTime);

                        stopwatch.Stop();

                        delta = stopwatch.ElapsedMilliseconds;
                        int sleepTime = TickTime - (int)delta;
                        if (sleepTime > 0) Thread.Sleep(sleepTime);

                        else Log.WriteLog("TickTime over");

                    }
                }
                catch (OperationCanceledException)
                {
                }
                finally
                {
                    await client.StopAsync();
                    Log.WriteLog("Client Stopped");
                }
            }

        }
    }
}