
namespace Game.Network
{
    public static class SessionIdGenerator
    {
        private static int _seq = 1;
        public static SessionId Get()
        {
            return new SessionId(++_seq);
        }
    }

    public static class SessionPlayerIdGenerator
    {
        
        private static int _seq = 1;
        public static SessionPlayerId Get()
        {
            return new SessionPlayerId(++_seq);
        }
    }
}