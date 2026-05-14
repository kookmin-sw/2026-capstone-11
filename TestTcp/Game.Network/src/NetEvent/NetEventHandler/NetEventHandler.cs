
using System.IO.Compression;
using System.Runtime.CompilerServices;

namespace Game.Network
{
    public interface INetReceiveEventHandler
    {
        public int HandlerId {get;}
        // Data
        public void OnReceive(ConnId connId, byte[] raw) {}
        public void OnRespond(ConnId connId, int queryNum, byte[] raw) {}
        public void OnQuery(ConnId connId, int queryNum, byte[] raw) {}
    }

    public interface INetControlEventHandler
    {
        // Control
        public void OnException(ConnId connId, byte[] raw, string msg) {}
        public void OnHello(ConnId connId, byte[] raw) {}
        public void OnDisconnect(ConnId connId, byte[] raw) {}
    }
    public interface INetEventHandler : INetReceiveEventHandler, INetControlEventHandler {}
}