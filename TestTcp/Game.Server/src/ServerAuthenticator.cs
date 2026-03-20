using Game.Network;
using Game.Network.Protocol;

namespace Game.Server
{
    public class ByPassAuthenticator : IAuthenticator
    {
        public AuthenticateInfo Authenticate(string connId, ConnectionInfo info)
            => new AuthenticateInfo(true);
    }

}