
namespace Game.Network.Service
{
    public class MatchRespondModule : IServiceModule
    {
        private DispatchMap _dispatch;
        private IPeerDictReader _other; 




        public void Init(ServiceContext_V2 context)
        {
            _dispatch = context.Dispatcher;
            _other = context.Other;


            // _dispatch.Register()
        }



    }
}