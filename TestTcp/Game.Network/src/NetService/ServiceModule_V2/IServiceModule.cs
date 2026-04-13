using System.ComponentModel;
using System.IO.Compression;

namespace Game.Network.Service
{
    public interface IServiceModule
    {
        void Init(ServiceContext_V2 context);
        void Tick(int delta) {}
        void Disable() {}
    }


}