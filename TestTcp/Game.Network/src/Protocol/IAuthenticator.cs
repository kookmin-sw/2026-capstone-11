
namespace Game.Network.Protocol
{
    public class AuthenticateInfo
    {
        public readonly bool IsAuth;
        public readonly string FailMsg;

        public AuthenticateInfo(bool isAuth, string failMsg = "") 
        { IsAuth = isAuth; FailMsg = failMsg;}
    }

    public interface IAuthenticator
    {
        public AuthenticateInfo Authenticate(string connId, ConnectionInfo info);
    }
}