
using System.IO.Compression;

namespace Game.Network.Service
{
    public interface IHostReader
    {
        public ConnId connId {get;}
        public bool HasHost {get;}
    }

    public interface IHostWriter : IHostReader
    {
        public void SetHost(ConnId connId);
        public void Clear();
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

        public void Clear() 
            => _hostConnId = ConnId.Default();

        public bool HasHost => _hostConnId != ConnId.Default();
    }
}