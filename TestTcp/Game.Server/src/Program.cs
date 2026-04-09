using System.Diagnostics;
using System.IO.Pipelines;
using System.Net.NetworkInformation;
using System.Net.Security;
using System.Threading.Tasks;
using Game.Network;
using Game.Network.Protocol;
using Game.Server.Chess;


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

            Session session = new(server);
            ChessGame game  = new(session);


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
                    game.Tick((int)delta);

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


