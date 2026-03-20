
using System.Net.Mime;
using Game.Server;

namespace Game.Network
{
    public abstract class ServiceModule
    {
        public abstract int HandlerId {get;}
        protected readonly INetAPI Net;
        protected readonly ServiceContext Context;

        protected ServiceModule(INetAPI net, ServiceContext context)
        {
            Context = context;
            Net = net;
        }
    }
}