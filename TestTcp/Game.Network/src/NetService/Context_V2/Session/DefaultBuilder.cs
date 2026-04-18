
using Game.Network;

namespace Game.Network
{
    public class DefaultBuilder : ISessionBuilder
    {
        public Session? BuildSession(ISessionPort port, SessionId id)
        {
            return new Session(port, id, 2, 2);
        }
        
        public Session? BuildSession(SessionId id)
        {
            return new Session(new DefaultPort(), id, 2, 2);
        
        }
    }
}