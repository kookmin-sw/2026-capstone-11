
using System.Net.NetworkInformation;

namespace Game.Network.Protocol
{
    public class PingInfo
    {
        public long currentPingResult;
        public int failureCount;

        public PingInfo(int maxFailCount = 3)
        {
            currentPingResult = 0;
            failureCount = maxFailCount;
        }
    };
}