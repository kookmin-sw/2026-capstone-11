
namespace Game.Network.Protocol
{
    public struct SessionBindInfo
    {
        private bool _isBind;
        private SessionId _bindSession;
        private SessionPlayerId _bindSessionPlayer;

        public SessionBindInfo(bool isBind, SessionId sessionToBind, SessionPlayerId playerToBind)
        {
            _isBind = isBind;
            _bindSession = sessionToBind;
            _bindSessionPlayer = playerToBind;
        }

        public bool IsBind => _isBind;
        public SessionId SessionId => _bindSession;
        public SessionPlayerId PlayerId => _bindSessionPlayer; 
    } 
}