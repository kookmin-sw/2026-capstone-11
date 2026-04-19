using System;
using System.Collections.Generic;
using System.IO.Compression;

namespace Game.Network.Service
{
    public interface IServiceEventPublisher
    {
        void PublishEnterEvents(IPeerReader peer);
        void PublishOutEvents(IPeerReader peer);    
    }

    public interface IServiceEventListener
    {
        void AddPeerEnterListener(Action<IPeerReader> listener);
        void RemovePeerEnterListener(Action<IPeerReader> listener);
        void AddPeerOutListener(Action<IPeerReader> listener);
        void RemovePeerOutListener(Action<IPeerReader> listener);
    }


    public class ServiceEventBridge : IServiceEventListener, IServiceEventPublisher
    {
        private List<Action<IPeerReader>> _peerEnterEvents = new();
        private List<Action<IPeerReader>> _peerOutEvents = new();

        public void AddPeerEnterListener(Action<IPeerReader> listener)
            => _peerEnterEvents.Add(listener);

        public void RemovePeerEnterListener(Action<IPeerReader> listener)
            => _peerEnterEvents.Remove(listener);

        public void AddPeerOutListener(Action<IPeerReader> listener)
            => _peerOutEvents.Add(listener);

        public void RemovePeerOutListener(Action<IPeerReader> listener)
            => _peerOutEvents.Remove(listener);
    
        public void PublishEnterEvents(IPeerReader peer)
        {
            foreach (var events in _peerEnterEvents)
                events.Invoke(peer);
        }

        public void PublishOutEvents(IPeerReader peer)
        {
            foreach (var events in _peerOutEvents) 
                events.Invoke(peer);
        }
    };
}