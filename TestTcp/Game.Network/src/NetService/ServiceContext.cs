

using System.Net.NetworkInformation;
using Game.Network.Protocol;

namespace Game.Network
{
    public class ServiceInfo
    {
        public ConnectionInfo connInfo;
        public PingInfo pingInfo;
        public AuthenticateInfo authInfo;
        public ServiceInfo(ConnectionInfo conn, PingInfo ping, AuthenticateInfo auth) 
        { connInfo = conn; pingInfo = ping; authInfo = auth;}
    }

    public struct ServiceOption {}

    public class ServiceContext
    {
        public Dictionary<string, ServiceInfo> infoPage = new();
    }
}