
using System.Net.NetworkInformation;

namespace Game.Network.Protocol
{
    public class PingInfo
    {
        public long currentPingResult;
        public long lastPingTime;
        public int failureCount;

        public PingInfo(int maxFailCount)
        {
            currentPingResult = 0;
            lastPingTime = 0;
            failureCount = maxFailCount;
        }
    };
}