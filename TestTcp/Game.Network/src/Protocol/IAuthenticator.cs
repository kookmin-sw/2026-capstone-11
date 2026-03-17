
namespace Game.Network.Protocol
{
    public class AuthenticateInfo
    {
        public readonly bool IsAuth = false;
        public readonly string FailMsg = "";
    }

    public interface IAuthenticator
    {
        public AuthenticateInfo Authenticate(string connId, ConnectionInfo info);
    }
}