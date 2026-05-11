namespace Game.Network.Service
{
    public class MatchEnterRequest
    {
        public MatchId toEnter; 
    }

    public class MatchExitRequest
    {
        public MatchId toEnter; 
    }

    public class MatchListInfoRequest
    {
        
    }

    public class MatchRoomInfoRequest
    {
        
    }

    public class MatchCreateRequest
    {
        
    }

    public class MatchReadyRequest
    {
        public MatchId toEnter;
        public bool ready; 
    }
}