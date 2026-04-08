
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
        private ConnInfo _connInfo = new();
        private SessionInfo _sessionInfo = new();

        public IConnInfoReader connInfo => _connInfo;
        public ISessionInfoReader sessionInfo => _sessionInfo;

        public IConnInfoWriter connWriter => _connInfo;
        public ISessionInfoWriter sessionWriter => _sessionInfo;

    }
}