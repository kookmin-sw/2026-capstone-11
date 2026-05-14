
using System;

namespace Game.Network
{
    public class ServiceOption
    {
        public int maxConnPerService;
        public int maxSessionPerService;
        public int helloTimeOutMs;

        // Peer Life Time
        public int suspendTimeOutThres;
        public int disconnectTimeOutThres;

        // About Ping
        public int pingIntervalMs;
        public int pingTimeOutMs;

        public ServiceOption(
            int MaxConnPerService,
            int MaxSessionPerService,
            int HelloTimeOutMs,
            int PingIntervalMs,
            int PingTimeOutMs,
            int SuspendTimeOutThres,
            int DisconnectTimeOutThres

        )
        {
            maxConnPerService = MaxConnPerService;
            maxSessionPerService = MaxSessionPerService;
            helloTimeOutMs = HelloTimeOutMs;
            
            pingIntervalMs = PingIntervalMs;
            pingTimeOutMs = PingTimeOutMs;

            if (SuspendTimeOutThres > DisconnectTimeOutThres) throw new InvalidOperationException();

            suspendTimeOutThres = SuspendTimeOutThres;
            disconnectTimeOutThres = DisconnectTimeOutThres; 

        }

    }
}