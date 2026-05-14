
using System;
using System.Net.Sockets;

namespace Game.Network
{
    public interface ISessionPort
    {
        void SendPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw) {}
        void QueryPlayer(SessionId sessionId, SessionPlayerId receiver, byte[] raw, long timeOutMs
                        , Action<byte[]> succAction, Action timeOutAction) {}
        void SendHost(SessionId sessionId, byte[] raw) {}
        void QueryHost(SessionId sessionId, byte[] raw, long timeOutMs
                        , Action<byte[]> succAction, Action timeOutAction) {}
    }
}