
namespace Game.Network
{
    public class ServiceOption
    {
        public int maxConnPerService;
        public int maxSessionPerService;
        public int helloTimeOutMs;

        // About Ping
        public int pingIntervalMs;
        public int pingTimeOutMs;
        public int pingFailCountToDisconnect;

        public ServiceOption(
            int MaxConnPerService,
            int MaxSessionPerService,
            int HelloTimeOutMs,
            int PingIntervalMs,
            int PingTimeOutMs,
            int PingFailCountToDisconnect
        )
        {
            maxConnPerService = MaxConnPerService;
            maxSessionPerService = MaxSessionPerService;
            helloTimeOutMs = HelloTimeOutMs;
            
            pingIntervalMs = PingIntervalMs;
            pingTimeOutMs = PingTimeOutMs;
            pingFailCountToDisconnect = PingFailCountToDisconnect;
        }

    }
}