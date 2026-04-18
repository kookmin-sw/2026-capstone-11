

using System.Reflection;
using Game.Network.Service;

namespace Game.Network
{
    public class ServiceManager
    {
        private Dictionary<Type, IServiceModule> _modules = new();

        // private List<IServiceModule> _serviceModules;
        private ServiceContext_V2 _context;

        public ServiceManager(INetAPI net, 
                            ISessionBuilder builder, 
                            ISessionPort port, 
                            ConnInfo selfConnInfo,
                            ServiceOption opt)
        {
            _context = new(net, builder, port, selfConnInfo, opt);
        }

        public void AddModule<T>() where T : IServiceModule, new()
        {
            T module = new();
            _modules[typeof(T)] = module;
            module.Init(_context);
        }

        public void RemoveAll()
        {
            foreach (var module in _modules.Values) 
                module.Disable();
            
            _modules.Clear();
        }

        public void Tick(int delta)
        {
            foreach (var module in _modules.Values) 
                module.Tick(delta);
        }

        public T GetModule<T>() where T : class, IServiceModule
        {
           if (_modules.TryGetValue(typeof(T), out var module)) return (T)module;
           throw new InvalidOperationException($"{typeof(T)} not Registered"); 
        }

        public string GetState() => _context.GetState();
    }

}