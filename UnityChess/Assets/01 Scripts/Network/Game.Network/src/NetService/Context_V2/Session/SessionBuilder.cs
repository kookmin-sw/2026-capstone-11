
namespace Game.Network
{
    public interface ISessionBuilder
    {
        /// <summary>
        /// null if Fail to Build Session
        /// </summary>
        /// <param name="port"></param>
        /// <param name="id"></param>
        /// <returns></returns>
        public Session? BuildSession(ISessionPort port, SessionId id);
        
        public Session? BuildSession(SessionId id);
    }
}