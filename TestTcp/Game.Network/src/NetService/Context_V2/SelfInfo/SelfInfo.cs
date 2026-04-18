
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public interface ISelfReader
    {
        public IConnInfoReader connInfo { get; }
        public ISessionInfoReader sessionInfo { get; }
    }

    public interface ISelfWriter : ISelfReader
    {
        public IConnInfoWriter connWriter { get; }
        public ISessionInfoWriter sessionWriter { get; }
    }


    public class SelfInfo : ISelfWriter
    {
        private ConnInfo _connInfo;
        private SessionInfo _sessionInfo;
        public SelfInfo(ConnInfo connInfo)
        {
            _connInfo = connInfo;
            _sessionInfo = new();
        } 
        public IConnInfoReader connInfo => _connInfo;
        public ISessionInfoReader sessionInfo => _sessionInfo;

        public IConnInfoWriter connWriter => _connInfo;
        public ISessionInfoWriter sessionWriter => _sessionInfo;

    }
}