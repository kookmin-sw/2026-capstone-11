

using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography.X509Certificates;

namespace Game.Network.Service
{
    public class MatchList
    {
        private List<Match> _matches = new(); 
        private int _maxPlayerPerMatch = 2;


        public Guid CreateMatch(Peer creater, int MaxPlayer)
        {
            var match = new Match();
            match.maxPlayer = MaxPlayer;
            match.players.Add(new PlayerRegistery(creater));
            _matches.Add(match);
            return match.MatchId;
        }

        public bool EnterMatch(Guid matchId, Peer peer)
        {
            Match? toEnter = _matches.FirstOrDefault(x => x.MatchId == matchId);
            
            if (toEnter == null 
                || toEnter.players.Count >= toEnter.maxPlayer
                || toEnter.players.Exists(x => x._peer.connId == peer.connId)) 
                return false;
        
            toEnter.players.Add(new PlayerRegistery(peer));
            return true;
        }

        public bool SetReady(Guid matchId, Peer peer, bool isReady)
        {
            Match? match = _matches.FirstOrDefault(x => x.MatchId == matchId);
            
            if (match == null) return false;
            var player = match.players.FirstOrDefault(x => x._peer.connId == peer.connId);

            if (player == null) return false;
            
            player.ready = true;
            return true;
        }

        public void ExitMatch(Guid matchId, Peer peer)
        {
            Match? match = _matches.FirstOrDefault(x => x.MatchId == matchId);
            if (match == null) return;
            
            var player = match.players.FirstOrDefault(x => x._peer.connId == peer.connId);
            if (player == null) return;

            match.players.Remove(player);
        }

    }
}