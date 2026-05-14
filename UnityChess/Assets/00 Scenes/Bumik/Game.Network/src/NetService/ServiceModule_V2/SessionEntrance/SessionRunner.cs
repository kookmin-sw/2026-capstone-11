
namespace Game.Network.Service
{
    public class SessionRunner : IServiceModule
    {
        private IGameReader _games;

        public void Init(ServiceContext_V2 context)
        {
            _games = context.Games;
        }

        public void Tick(int delta)
        {

        } 
    }
}