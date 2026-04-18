
using Game.Network;

namespace Game.Network
{
    public class DefaultPort : ISessionPort
    {
        public void SendPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw) {}
        public void QueryPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw, long timeOutMs
                               , Action<byte[]> succAction, Action timeOutAction) {}
        public void SendHost(SessionId sessionId, byte[] raw) {}
        public void QueryHost(SessionId sessionId, byte[] raw, long timeOutMs
                            , Action<byte[]> succAction, Action timeOutAction) {}
    }
}