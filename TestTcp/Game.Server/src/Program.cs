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
using Microsoft.Playfab.Gaming.GSDK.CSharp;
using SeaEngine.Common;
using SeaEngine.Logger;


namespace Game.Server
{
    class Program
    {
        public const int TickTime = 15;
        public const int ServerKillTimer = 30000;
        static async Task Main()
        {
            Log.SetLogger(GameserverSDK.LogMessage);

            var cts = new CancellationTokenSource();

            bool localMode = Environment.GetEnvironmentVariable("LOCAL_DEV") == "1";

            GameserverSDK.LogMessage("Before server.Start()");    

            var PlayfabRunner = new PlayfabRun(cts, 9000, localMode);

            GameserverSDK.LogMessage("After server.Start()");

            // Initalization
            var server = NetworkManager.CreateNetworkManager(PlayfabRunner.GamePort, 10);
            server.Start();

            var opt = new ServiceOption(
                MaxConnPerService: 2,
                MaxSessionPerService: 2,
                HelloTimeOutMs: 3000,
                PingIntervalMs: 3000,
                PingTimeOutMs: 2500,
                SuspendTimeOutThres: 5000,
                DisconnectTimeOutThres: 10000
            );

            var host = new HostService(server,
                                        new DefaultBuilder(),
                                        new DefaultPort(),
                                        "HostServer",
                                        "DevID",
                                        "DevVersion"
                                        , opt);

            Session session = new(server);
            ChessGame game = new(session);

            GameserverSDK.LogMessage("Before ReadyForPlayers()");
            // Check Ready
            if (!PlayfabRunner.ReadyForPlayers())
            {
                await server.StopAsync();
                return;
            }

            if (localMode)
            {

                var inputTask = Task.Run(() =>
                {
                    while (!cts.IsCancellationRequested)
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
            }

            try
            {
                var stopwatch = new Stopwatch();
                long delta = 0;
                int kill_timer = 0;

                Console.WriteLine("Server Running");

                while (!cts.IsCancellationRequested)
                {
                    if (!server.TryGetConnIdList(2, out var list))
                    {
                        kill_timer += TickTime;
                        if (kill_timer > ServerKillTimer) cts.Cancel();
                    }
                    else kill_timer = 0;


                    stopwatch.Restart();

                    server.Tick();
                    game.Tick(TickTime);
                    host.Tick(TickTime);

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


