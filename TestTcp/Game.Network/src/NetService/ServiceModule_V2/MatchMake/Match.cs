
using System;
using System.Collections.Generic;

namespace Game.Network.Service
{
    public class Match
    {
        public Guid MatchId = Guid.NewGuid();
        public int maxPlayer = 0;
        public List<PlayerRegistery> players = new(); // peer, ready
        public List<Peer> observer = new();
    }

    public class PlayerRegistery
    {
        public Peer _peer;
        public bool ready = false;

        public PlayerRegistery(Peer peer)
        {
            _peer = peer;
        }
    }
}