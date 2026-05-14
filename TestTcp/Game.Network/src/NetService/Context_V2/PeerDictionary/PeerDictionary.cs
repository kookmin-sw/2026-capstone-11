using Game.Network.Protocol;
using System;
using System.Collections.Generic;
using System.Linq;

namespace Game.Network.Service
{
    public interface IPeerDictReader
    {
        bool TryReadPeer(ConnId connId, out IPeerReader peer);
        IReadOnlyCollection<IPeerReader> PeerReaderList();
        bool HasPeer(ConnId connId); 
    }

    public interface IPeerDictWriter : IPeerDictReader
    {
        void AddPeer(ConnId connId, Peer peer);
        void AddPeer(Peer peer);
        bool RemovePeer(ConnId connId, out Peer peer);
        bool RemovePeer(ConnId connId);
        bool TryWritePeer(ConnId connId, out IPeerWriter peer);
        IReadOnlyCollection<IPeerWriter> PeerWriterList();
    }

    public interface IPeerDictSessionWriter : IPeerDictReader
    {
        bool TryGetSession(ConnId connId, out ISessionInfoWriter bindInfo);
    }

    public interface IPeerDictInfoWriter : IPeerDictReader
    {
        bool TryGetInfo(ConnId connId, out IConnInfoWriter info);
    }


    public class PeerDictionary : IPeerDictWriter
                                , IPeerDictSessionWriter
                                , IPeerDictInfoWriter
    {
        private Dictionary<ConnId, Peer> _dictonary = new();

        // Reader
        public bool HasPeer(ConnId connId) 
            => _dictonary.ContainsKey(connId);
        public bool TryReadPeer(ConnId connId, out IPeerReader reader)
        {
            if (_dictonary.TryGetValue(connId, out Peer peer))
            {
                reader = peer;
                return true;
            }
            reader = null;
            return false;
        }
        public IReadOnlyCollection<IPeerReader> PeerReaderList()
            => _dictonary.Values;
        
        public IReadOnlyCollection<IPeerWriter> PeerWriterList()
            => _dictonary.Values;

        //Writer
        public void AddPeer(ConnId connId, Peer peer)
            => _dictonary.Add(connId, peer);
        
        public void AddPeer(Peer peer) 
            => _dictonary.Add(peer.connId, peer);

        public bool RemovePeer(ConnId connId, out Peer peer)
            => _dictonary.Remove(connId, out peer);

        public bool RemovePeer(ConnId connId)
            => _dictonary.Remove(connId);

        public bool TryWritePeer(ConnId connId, out IPeerWriter writer)
        {
            if (_dictonary.TryGetValue(connId, out Peer peer))
            {
                writer = peer;
                return true;
            }
            writer = null;
            return false;
        }
        public bool TryGetSession(ConnId connId, out ISessionInfoWriter info)
        {
            if (_dictonary.TryGetValue(connId, out Peer peer))
            {
                info = peer.sessionWriter;
                return true;
            }
            info = null;
            return false;
        }

        public bool TryGetInfo(ConnId connId, out IConnInfoWriter info)
        {
            if (_dictonary.TryGetValue(connId, out Peer peer))
            {
                info = peer.connWriter;
                return true;
            }
            info = null;
            return false;
        }
    }

}