using Game.Network;
using Microsoft.Playfab.Gaming.GSDK.CSharp;

namespace Game.Server
{
    // PlayFab GSDK Processor + Window(Standby) mode lifecycle wrapper.
    // Order: RegisterCallbacks → Start() → GetConfigSettings() → ReadyForPlayers()
    public class PlayfabRun
    {
        // Port name configured in the PlayFab build's port mapping.
        private const string PortKey = "game_port";

        private readonly CancellationTokenSource _cts;
        public readonly bool _localMode;

        public int GamePort { get; }

        public PlayfabRun(CancellationTokenSource cts, int fallbackPort, bool localMode = false)
        {
            _cts = cts;
            _localMode = localMode;

            if (localMode)
            {
                GamePort = fallbackPort;
                return;
            }

            GameserverSDK.RegisterShutdownCallback(OnShutdown);
            GameserverSDK.RegisterHealthCallback(OnHealthCheck);

            GameserverSDK.Start();

            var config = GameserverSDK.getConfigSettings();

            if (config != null &&
                config.TryGetValue(PortKey, out var raw) &&
                int.TryParse(raw, out var port))
            {
                GamePort = port;
                Log.WriteLog($"MPS port resolved. PortKey={PortKey}, GamePort={GamePort}");
            }
            else
            {
                Log.WriteLog($"MPS port resolve failed. PortKey={PortKey}");

                if (config != null)
                {
                    foreach (var kv in config)
                    {
                        Log.WriteLog($"GSDK Config: {kv.Key} = {kv.Value}");
                    }
                }

                throw new Exception($"MPS port not found. PortKey={PortKey}");
            }
        }
        // Blocks until PlayFab allocates this server (Window/Standby).
        // Returns false → PlayFab will not allocate; server should shut down.
        public bool ReadyForPlayers() => _localMode || GameserverSDK.ReadyForPlayers();

        private void OnShutdown() => _cts.Cancel();

        private bool OnHealthCheck() => !_cts.IsCancellationRequested;
    }
}
