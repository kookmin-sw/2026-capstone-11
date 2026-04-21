

using System.Reflection;
using Game.Network.Service;

namespace Game.Network
{
    public class ServiceManager
    {
        private List<IServiceModule> _serviceModules;
        private ServiceContext_V2 context;

        public void AddModule(IServiceModule module)
        {
            _serviceModules.Add(module);
            module.Init(context);
        } 

        public void AddModule<T>() where T : IServiceModule, new()
        {
            T module = new();
            _serviceModules.Add(module);
            module.Init(context);
        }

        public void RemoveAll()
        {
            foreach (var module in _serviceModules) 
                module.Disable();
            
            _serviceModules.Clear();
        }

        public void Tick(int delta)
        {
            foreach (var module in _serviceModules) 
                module.Tick(delta);
        }
    }

}