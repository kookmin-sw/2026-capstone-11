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
        public ChessGame(Session session)
        {

            _session = session;
            _session.Events.OnPlayerEnter = EnterPlayer;
            _session.Events.OnPlayerExit = ExitPlayer;
        }

        public void InitGame(string p1 = "1", string p2 = "2")
        {
            _seaGame = new(new SeaEngine.CardManager.CardLoader(""), new SimpleLogger(), p1, p2);
            _seaGame.Init(
                        "[\"Or_L\", \"Or_B\", \"Or_R\", \"Or_N\", \"Or_P\", \"Or_P\", \"Or_P\"]", 
                        "[\"Cl_L\", \"Cl_B\", \"Cl_R\", \"Cl_N\", \"Cl_P\", \"Cl_P\", \"Cl_P\"]"
                        );
        }

        public void Tick(int delta)
        {
            if (_isGameRunnable && _hasSomethingToSend)
            {
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
            _players.Remove(name);
        }

        private void QueryCallBack(QueryTaskResult result)
        {
            if (result.IsResponded)
            {
                Uid toAct = Uid.Parse(Encoding.UTF8.GetString(result.AnswerRaw));
                Log.WriteLog($"[ChessGame] Use Action | Uid: {toAct}");
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