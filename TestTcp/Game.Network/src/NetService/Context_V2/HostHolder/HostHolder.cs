
using System.IO.Compression;

namespace Game.Network.Service
{
    public interface IHostReader
    {
        public ConnId connId {get;}
    }

    public interface IHostWriter : IHostReader
    {
        public void SetHost(ConnId connId);
    }

    public class HostHolder : IHostWriter
    {
        private ConnId _hostConnId;
        public HostHolder()
        {
            _hostConnId = ConnId.Default();
        }

        public ConnId connId => _hostConnId;
        public void SetHost(ConnId connId) 
            => _hostConnId = connId;
    }
}