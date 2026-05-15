

using System;
using System.Collections.Generic;
using System.Linq;

namespace Game.Network.Service
{
    public class MatchList
    {
        private List<Match> _matches = new(); 
        private int _maxPlayerPerMatch = 2;


        public MatchId CreateMatch(Peer creater, int MaxPlayer)
        {
            var match = new Match();
            match.maxPlayer = Math.Clamp(MaxPlayer, 1, _maxPlayerPerMatch);

            match.players.Add(new PlayerRegistery(creater));
            _matches.Add(match);
            return match.Id;
        }

        public bool EnterMatch(MatchId matchId, Peer peer)
        {
            Match? toEnter = _matches.FirstOrDefault(x => x.Id == matchId);
            
            if (toEnter == null 
                || toEnter.players.Count >= toEnter.maxPlayer
                || toEnter.players.Exists(x => x._peer.connId == peer.connId)) 
                return false;
        
            toEnter.players.Add(new PlayerRegistery(peer));
            return true;
        }

        public bool SetReady(MatchId matchId, Peer peer, bool isReady)
        {
            Match? match = _matches.FirstOrDefault(x => x.Id == matchId);
            
            if (match == null) return false;
            var player = match.players.FirstOrDefault(x => x._peer.connId == peer.connId);

            if (player == null) return false;
            
            player.ready = isReady;
            return true;
        }

        public void ExitMatch(MatchId matchId, Peer peer)
        {
            Match? match = _matches.FirstOrDefault(x => x.Id == matchId);
            if (match == null) return;
            
            var player = match.players.FirstOrDefault(x => x._peer.connId == peer.connId);
            if (player == null) return;

            match.players.Remove(player);

            if (match.players.Count <= 0) _matches.Remove(match);
        }

    }
}