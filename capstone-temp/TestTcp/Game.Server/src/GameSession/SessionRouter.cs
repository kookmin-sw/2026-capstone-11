using Game.Network;

namespace Game.Server
{

    public class SessionRouter
    {
        private Dictionary<string, ConnId> _player_connDict = new(); // (PlayerName, ConnectoinId)
        private Dictionary<ConnId, string> _conn_playerDict = new(); // (PlayerName, ConnectoinId)


        public Dictionary<string, ConnId>.ValueCollection IdList => _player_connDict.Values;
        public Dictionary<ConnId, string>.ValueCollection playerList => _conn_playerDict.Values;

        public bool TryAdd(string name, ConnId id)
        {
            if (!_player_connDict.TryAdd(name, id))
                return false;
            if (!_conn_playerDict.TryAdd(id, name))
            {
                _player_connDict.Remove(name);
                return false;
            }
            return true;
        }
        public bool TryRemove(string name)
        {
            if (!_player_connDict.Remove(name, out var id))
                return false;
            
            if (!_conn_playerDict.Remove(id, out var na))
            {
                _player_connDict[name] = id;
                return false;
            }
            return true;
        }

        public bool TryRemove(ConnId id)
        {
            if (!_conn_playerDict.Remove(id, out var name))
                return false;
            if (!_player_connDict.Remove(name, out var id_2))
            {
                _conn_playerDict[id] = name;
                return false;
            }
            return true;
        }
        public bool TryRoute(ConnId id, out string name)
            => _conn_playerDict.TryGetValue(id, out name);
        public bool TryRoute(string name, out ConnId id) 
            => _player_connDict.TryGetValue(name, out id);
    }
}