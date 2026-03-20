
namespace Game.Network
{
    public class SessionPlayerInfo
    {
        // 여긴 로직 담당이.

    }

    /// <summary>
    /// 로직에서 세션 특정을 위한 id
    /// </summary>
    public struct SessionId : IEquatable<SessionId>
    {
        public readonly int Value;
        public SessionId(int v) { Value = v; }

        public bool Equals(SessionId other) => Value == other.Value;
        public override bool Equals(object? obj) => obj is SessionId other && Equals(other);
        public override int GetHashCode() => Value;

        public static bool operator ==(SessionId id_1, SessionId id_2) => id_1.Equals(id_2);

        public static bool operator !=(SessionId id_1, SessionId id_2) => !id_1.Equals(id_2);
    }

    /// <summary>
    /// 로직에서 플에이어 특정을 위한 id. 
    /// </summary>
    public struct SessionPlayerId : IEquatable<SessionPlayerId>
    {
        public readonly int Value;
        public SessionPlayerId(int v) { Value = v; }

        public bool Equals(SessionPlayerId other) => Value == other.Value;
        public override bool Equals(object? obj) => obj is SessionPlayerId other && Equals(other);
        public override int GetHashCode() => Value;

        public static bool operator ==(SessionPlayerId id_1, SessionPlayerId id_2) => id_1.Equals(id_2);

        public static bool operator !=(SessionPlayerId id_1, SessionPlayerId id_2) => !id_1.Equals(id_2);
    }


    public class SessionContext
    {
        private SessionId _id;
        private Dictionary<SessionPlayerId, SessionPlayerInfo> _playersInSession;

        // Some Other CommonInfo For Logic

    }
}