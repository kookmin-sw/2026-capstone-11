using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO.Compression;
using Game.Network.Service;


namespace Game.Network.Service
{

    public class DispatchMap 
    {
        private Dictionary<int, DispatcherRegistery> _dispatchMap = new();

        public void Register(int id, DispatcherRegistery registery)
        {
            _dispatchMap[id] = registery;
        }
        public bool TryDispatch(int id, out DispatcherRegistery registery) 
        => _dispatchMap.TryGetValue(id, out registery);

        public void Deregister(int id)
        => _dispatchMap.Remove(id);
    
    }
}