using System.Data.Common;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Game.Network;
using Game.Network.Service;

namespace Game.Client
{
    class Program
    {
        public const int TickTime = 15;
        static async Task Main()
        {
            Log.SetLogger(Console.WriteLine);

            var server = NetworkManager.CreateNetworkManager(0, 10);
            server.Start();

            var opt = new ServiceOption(
                MaxConnPerService: 2,
                MaxSessionPerService: 2,
                HelloTimeOutMs: 3000,
                PingIntervalMs: 3000,
                PingTimeOutMs: 2500,
                PingFailCountToDisconnect: 2
            );

            var client = new ClientService(server, 
                                            new DefaultBuilder(), 
                                            new DefaultPort(), 
                                            "TestConsole",
                                            "TestConsoleId",
                                            "DevVersion",
                                            opt);

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
                        Log.WriteLog("Client State : ");
                        Log.WriteLog(client.GetState());
                    }
                    else if (line != null && line.Trim().Equals("p", StringComparison.OrdinalIgnoreCase))
                    {
                        client.PeerEnter.Request(
                        (rsp) =>
                        {
                            if(rsp.IsSucc)
                            {
                                Console.WriteLine("Succ");
                                Console.WriteLine(rsp.RemotePeerInfo.PlatformName);
                                Console.WriteLine(rsp.RemotePeerInfo.AccountId);
                                Console.WriteLine(rsp.RemotePeerInfo.AppVersion);
                            }
                            else
                            {
                                Console.WriteLine(rsp.Msg);
                            }

                        },
                        (error) =>
                        {
                            Console.WriteLine($"Failed. Messge {error}");

                        }
                        );
                    }
                    else if (line != null && line.Trim().Equals("g", StringComparison.OrdinalIgnoreCase))
                    {
                        client.Session.Request(
                            new SessionReq(SessionReqType.ReqEnter, new SessionId(99), SessionPlayerId.Default),
                        (rsp) =>
                        {
                            if(rsp.type == SessionRspType.Accepted)
                            {
                                Console.WriteLine("Succ");
                                Console.WriteLine(rsp.sessionId);
                                Console.WriteLine(rsp.playerId);
                            }
                            else
                            {
                                Console.WriteLine("Rejected");
                            }

                        },
                        (error) =>
                        {
                            Console.WriteLine($"Failed. Messge {error}");

                        }
                        );
                    }
                }
            });

            try
            {
                var stopwatch = new Stopwatch();
                long delta = 0;

                Console.WriteLine("Client Running");

                Console.WriteLine("Client Start To Local");

                await server.ConnectTo("127.0.0.1", 9000, 3000);

                while (!cts.IsCancellationRequested)
                {
                    stopwatch.Restart();

                    server.Tick();
                    client.Tick(TickTime);


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


