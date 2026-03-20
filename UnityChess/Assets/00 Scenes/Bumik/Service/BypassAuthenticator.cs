using System.Runtime.InteropServices.WindowsRuntime;
using Game.Network.Protocol;
using UnityEngine;

public class BypassAuthenticator : IAuthenticator
{   
    public AuthenticateInfo Authenticate(string connId, ConnectionInfo info) 
        => new AuthenticateInfo(true, "Just Bypass");
}
