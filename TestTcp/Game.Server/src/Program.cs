using System.Diagnostics;
using System.IO.Pipelines;
using System.Net.NetworkInformation;
using System.Net.Security;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Game.Network;
using Game.Network.Protocol;
using Game.Network.Service;
using Game.Server.Chess;
using SeaEngine.Common;
using SeaEngine.Logger;


namespace Game.Server
{
    class Program
    {
        public const int TickTime = 15;
        static async Task Main()
        {
            Log.SetLogger(Console.WriteLine);

            var server = NetworkManager.CreateNetworkManager(TransferConfig.ServerPortNum, 10);
            server.Start();

            var opt = new ServiceOption(
                MaxConnPerService: 2,
                MaxSessionPerService: 2,
                HelloTimeOutMs: 3000,
                PingIntervalMs: 3000,
                PingTimeOutMs: 2500,
                PingFailCountToDisconnect: 2 
            );
            
            // var host = new HostService(server, 
            //                             new DefaultBuilder(), 
            //                             new DefaultPort(), 
            //                             "HostServer",
            //                             "DevID",
            //                             "DevVersion"
            //                             , opt);

            Session session = new(server);
            ChessGame game  = new(session);

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

                        // Log.WriteLog("Service State : ");
                        // Log.WriteLog(host.GetState());
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
                    game.Tick(TickTime);
                    // host.Tick(TickTime);

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
    }

}


