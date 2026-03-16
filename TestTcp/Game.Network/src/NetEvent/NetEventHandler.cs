
using System.IO.Compression;
using System.Runtime.CompilerServices;

namespace Game.Network
{
    public static class NetEventHandlerId
    {
        public const int System = 0;
        public const int PingPong = 1;
    }

    public interface INetEventHandler
    {        
        // Data
        public void OnReceive(string ConnId, byte[] raw) {}
        public void OnRespond(string ConnId, int queryNum, byte[] raw) {}
        public void OnQuery(string ConnId, int queryNum, byte[] raw) {}

        // Control
        public void OnException(string ConnId, byte[] raw, string msg) {}
        public void OnHello(string ConnId, byte[] raw) {}
        public void OnDisconnect(string ConnId, byte[] raw) {}
    }
}