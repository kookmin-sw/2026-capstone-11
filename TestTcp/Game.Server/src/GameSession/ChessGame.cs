using System.Formats.Asn1;
using System.Text;
using Game.Network;
using SeaEngine.Common;
using SeaEngine.Logger;

namespace Game.Server.Chess
{
    public class ChessGame
    {
        private SeaEngine.Game _seaGame;
        private const int ActionTimeOutMs = 9999;
        private List<string> _players = new(2);
        private bool _hasSomethingToSend = false;
        private Session _session;

        private bool _isGameRunnable;
        private bool _startClean;
        public ChessGame(Session session)
        {

            _session = session;
            _session.Events.OnPlayerEnter = EnterPlayer;
            _session.Events.OnPlayerExit = ExitPlayer;
        }

        public void InitGame(string p1 = "1", string p2 = "2")
        {
            _seaGame = new(new SeaEngine.CardManager.CardLoader(File.ReadAllLines(Setting.DBPath)), new SimpleLogger(), p1, p2);
            _seaGame.Init(
                        "[\"Or_L\", \"Or_B\", \"Or_R\", \"Or_N\", \"Or_P\", \"Or_P\", \"Or_P\"]",
                        "[\"Cl_L\", \"Cl_B\", \"Cl_R\", \"Cl_N\", \"Cl_P\", \"Cl_P\", \"Cl_P\"]"
                        );
        }

        public void Tick(int delta)
        {
            if (_startClean) CleanGame();

            if (_isGameRunnable && _hasSomethingToSend)
            {
                if (_seaGame.Data.Winner != null)
                    _startClean = true;
                
                _session.BroadCastPlayer(Encoding.UTF8.GetBytes(_seaGame.Serialize()));

                _session.QueryPlayer(
                    _seaGame.Data.ActivePlayer.Id,
                    Encoding.UTF8.GetBytes(_seaGame.Serialize()),
                    ActionTimeOutMs,
                    QueryCallBack
                );

                _hasSomethingToSend = false;
            }
        }

        private void EnterPlayer(string name)
        {
            if (_players.Count < 2)
                _players.Add(name);

            if (_players.Count == 2)
            {
                InitGame(_players[0], _players[1]);
                _isGameRunnable = true; _hasSomethingToSend = true;
            }
        }
        private void ExitPlayer(string name)
        {
            if (_isGameRunnable)
            {
                Log.WriteLog($"[ChessGame] : Player : {name} disconnect while game run. terminate game unsafely");
                CleanGame();
            }

            else _players.Remove(name);
        }

        private void CleanGame()
        {
            _players.Clear();
            _session.Clear();
            _isGameRunnable = false;
            _hasSomethingToSend = false;
            _startClean = false;

            _session.Events.OnPlayerEnter = EnterPlayer;
            _session.Events.OnPlayerExit = ExitPlayer;
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


    }

}