using System.Formats.Asn1;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using Game.Network;
using Game.Network.Service;
using Newtonsoft.Json;
using SeaEngine.Common;
using SeaEngine.GameDataManager.Components;
using SeaEngine.Logger;

namespace Game.Server.Chess
{
    public class ChessGame
    {
        private enum GameState {WaitForPlayer, Starting, Running, Stopped }

        public enum PlayerState { Entered, Prepare, Ready, Playing }

        public class PlayerEntry
        {
            public string Name = "";
            public string Deck = "";
            public PlayerState State = PlayerState.Entered;
            public PlayerEntry(string name = "", string deck = "")
            {
                Name = name; Deck = deck;
            }
        }


        private SeaEngine.Game _seaGame;
        private const int ActionTimeOutMs = 9999;
        private List<PlayerEntry> _players; // Name, Deck, State
        private bool _hasSomethingToSend = false;
        private Session _session;
        private GameState gameState = GameState.WaitForPlayer;



        private int _cleanCountDown = 0;
        private int _startCountDown = 0;
        private const int TimeToStartClean = 500;
        private const int TimeToStartRunning = 500;

        public ChessGame(Session session)
        {
            _players = new(2);

            _session = session;
            _session.Events.OnPlayerEnter = EnterPlayer;
            _session.Events.OnPlayerExit = ExitPlayer;
            _session.Events.OnSessionPlayerDataUpdate = HandleUserDataUpdate;
            _session.Events.OnSessionPlayerReady = HandleUserReady;
            
        }

        public void InitGame(string p1 = "1", string p2 = "2", 
                            string d1 = "[\"Or_L\", \"Or_B\", \"Or_R\", \"Or_N\", \"Or_P\", \"Or_P\", \"Or_P\"]",
                            string d2 = "[\"Cl_L\", \"Cl_B\", \"Cl_R\", \"Cl_N\", \"Cl_P\", \"Cl_P\", \"Cl_P\"]")
        {
            _seaGame = new(new SeaEngine.CardManager.CardLoader(File.ReadAllLines(Setting.DBPath)), new SimpleLogger(), p1, p2);
            _seaGame.Init(d1, d2);
            _hasSomethingToSend = true;
        }

        public void StateTransit()
        {
            switch (gameState)
            {
                case GameState.WaitForPlayer:
                    if (_players.Count == 2 && _players.All(x => x.State == PlayerState.Ready))
                    {
                        InitGame(_players[0].Name, _players[1].Name, _players[0].Deck, _players[1].Deck);
                        gameState = GameState.Starting;
                    }
                    break;

                case GameState.Starting:
                    if (_startCountDown > TimeToStartRunning)
                    {
                        gameState = GameState.Running;
                        _startCountDown = 0;
                    }
                    break;

                case GameState.Running:
                    if (_players.Count < 2)
                    {
                        Log.WriteLog($"[ChessGame] : Player disconnect while game run. terminate game unsafely");
                        gameState = GameState.Stopped;
                    }

                    if (_seaGame.Data.Winner != null)
                    {
                        Log.WriteLog($"[ChessGame] : {_seaGame.Data.WinnerId} Win ! | Start Clean Game");
                        _session.BroadCastPlayer(Encoding.UTF8.GetBytes(_seaGame.Serialize()));
                        gameState = GameState.Stopped;
                    }
                    break;
                case GameState.Stopped:
                    if (_cleanCountDown > TimeToStartClean)
                    {
                        CleanGame();
                        _cleanCountDown = 0;
                        gameState = GameState.WaitForPlayer;
                    }
                    break;
            }
        }

        public void WaitTick() {}

        public void StartingTick(int delta)
        {
            _startCountDown += delta;
        }

        public void RunningTick()
        {
            if (_hasSomethingToSend)
            {
                _session.BroadCastPlayer(Encoding.UTF8.GetBytes(_seaGame.Serialize()));

                if (_seaGame.Data.Winner != null) {_hasSomethingToSend = false; return;}

                _session.QueryPlayer(
                    _seaGame.Data.ActivePlayer.Id,
                    Encoding.UTF8.GetBytes(_seaGame.Serialize()),
                    ActionTimeOutMs,
                    QueryCallBack
                );

                _hasSomethingToSend = false;
            }
        }

        public void StopTick(int delta)
        {
            _cleanCountDown += delta;
        }

        public void Tick(int delta)
        {
            switch (gameState)
            {
                case GameState.WaitForPlayer: WaitTick(); break;
                case GameState.Starting: StartingTick(delta); break;
                case GameState.Running: RunningTick(); break;
                case GameState.Stopped: StopTick(delta); break;
            }

            StateTransit();
        }

        private void EnterPlayer(string name)
        {
            if (_players.Count < 2)
            {
                var player = new PlayerEntry(name);
                _players.Add(player);
                Log.WriteLog($"[ChessGame] : New Player Enter {name}");
            }
        }
        private void ExitPlayer(string name)
        {
            var toDelete = _players.FirstOrDefault(x => x.Name == name);
            if (toDelete != null) _players.Remove(toDelete);
        }

        private void CleanGame()
        {
            _players.Clear();
            _session.Clear();
      
            _hasSomethingToSend = false;

            _session.Events.OnPlayerEnter = EnterPlayer;
            _session.Events.OnPlayerExit = ExitPlayer;
            _session.Events.OnSessionPlayerDataUpdate = HandleUserDataUpdate;
            _session.Events.OnSessionPlayerReady = HandleUserReady;
        }


        private void QueryCallBack(string playerName, QueryTaskResult result)
        {
            if (result.IsResponded && _seaGame.Data.ActivePlayerId == playerName)
            {
                Uid toAct = Uid.Parse(Encoding.UTF8.GetString(result.AnswerRaw));

                var action = _seaGame.Actions.FirstOrDefault(x => x.Guid == toAct);

                if (action == null) throw new InvalidOperationException($"Use of Invalid Action | Uid : {toAct}");

                Log.WriteLog($"[ChessGame] Use Action | {action.ToString()} ");
                _seaGame.UseAction(toAct);
            }
            else
            {
                Log.WriteLog($"[ChessGame] fail to get Rsp from {_seaGame.Data.ActivePlayerId}");
            }
            _hasSomethingToSend = true;
        }

        private SimpleRsp HandleUserDataUpdate(string name, SimpleReq req)
        {
            var player = _players.FirstOrDefault(x => x.Name == name);
            if (player == null) return SimpleRsp.Denied("Enter Session First");
            if (req.Msg == "") return SimpleRsp.Denied("Deck req not Found");

            player.Deck = req.Msg;
            player.State = PlayerState.Prepare;
            Log.WriteLog($"[ChessGame] :  Player-{name} Set Deck: {player.Deck}");

            return SimpleRsp.Accepted("Deck Set");
        }

        private SimpleRsp HandleUserReady(string name, SimpleReq req)
        {
            var player = _players.FirstOrDefault(x => x.Name == name);
            if (player == null) return SimpleRsp.Denied("Enter Session First");
            if (req.Msg == "") return SimpleRsp.Denied("Deck req not Found");

            player.State = PlayerState.Ready;
            Log.WriteLog($"[ChessGame] :  Player-{name} Ready");

            return SimpleRsp.Accepted("Player Now Ready");
        }  


    }

}