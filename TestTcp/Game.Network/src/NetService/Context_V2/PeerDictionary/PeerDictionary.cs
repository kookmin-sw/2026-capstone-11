using Game.Network.Protocol;

namespace Game.Network.Service
{
    public interface IPeerDictReader
    {
        bool TryReadPeer(ConnId connId, out IPeerReader peer);
        List<IPeerReader> ReadPeers();
        bool HasPeer(ConnId connId); 
    }

    public interface IPeerDictWriter : IPeerDictReader
    {
        void AddPeer(ConnId connId, Peer peer);
        void AddPeer(Peer peer);
        bool RemovePeer(ConnId connId, out Peer peer);
        bool RemovePeer(ConnId connId);
    }

    public interface IPeerDictSessionWriter : IPeerDictReader
    {
        bool TryGetSession(ConnId connId, out ISessionInfoWriter bindInfo);
    }

    public interface IPeerDictPingWriter : IPeerDictReader
    {
        bool TryGetPing(ConnId connId, out PingInfo bindInfo);
    }

    public interface IPeerDictInfoWriter : IPeerDictReader
    {
        bool TryGetInfo(ConnId connId, out IConnInfoWriter info);
    }




    public class PeerDictionary : IPeerDictWriter, IPeerDictSessionWriter, IPeerDictPingWriter, IPeerDictInfoWriter
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
        public List<IPeerReader> ReadPeers()
            => _dictonary.Values.ToList<IPeerReader>();

        //Writer
        public void AddPeer(ConnId connId, Peer peer)
            => _dictonary.Add(connId, peer);
        
        public void AddPeer(Peer peer) 
            => _dictonary.Add(peer.connId, peer);

        public bool RemovePeer(ConnId connId, out Peer peer)
            => _dictonary.Remove(connId, out peer);

        public bool RemovePeer(ConnId connId)
            => _dictonary.Remove(connId);

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

        public bool TryGetPing(ConnId connId, out PingInfo ping)
        {
            if (_dictonary.TryGetValue(connId, out Peer peer))
            {
                ping = peer.ping;
                return true;
            }
            ping = null;
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