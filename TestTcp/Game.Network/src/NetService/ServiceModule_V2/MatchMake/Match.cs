
using System;
using System.Collections.Generic;

namespace Game.Network.Service
{
    public class Match
    {
        public MatchId Id = MatchId.Get();
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

    public struct MatchId : IEquatable<MatchId>
    {
        public readonly int Value;
        public MatchId(int value) { Value = value; }

        private static int _seq = 1;

        public static MatchId Get()
            => new MatchId(_seq++);

        public static MatchId Default
            => new MatchId(0);

        public bool Equals(MatchId other) => Value == other.Value;
        public override bool Equals(object? obj) => obj is MatchId other && Equals(other);
        public override int GetHashCode()
        { 
            return Value.GetHashCode();;
        }
        public override string ToString()
        {
            return Value.ToString();
        }

        public static bool operator ==(MatchId id_1, MatchId id_2) => id_1.Equals(id_2);
        public static bool operator !=(MatchId id_1, MatchId id_2) => !id_1.Equals(id_2);

    }
}