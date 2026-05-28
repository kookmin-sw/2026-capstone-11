

namespace Game.Network.Protocol
{
    public class SessionBindInfo
    {
        public bool IsSessionBinded = false;
        public bool IsSessionEntered = false;
        public Session? session = null;
        public SessionId sessionId;
        public SessionPlayerId playerId;

        public SessionBindInfo()
        {
            
        }
    }
}