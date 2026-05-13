

using System.Data;

namespace Game.Network.Service
{
    public static class PacketId
    {
        public static class Constant
        {
            public const int EmptyAcceptPacket = 0x0000_0000;
            public const int SimpleReq = 0x0000_0001;
            public const int SimpleRsp = 0x0001_0001;
            public const int FailRsp = 0x0000_0002;

            public const int PeerEnterReq = 0x0000_0003;
            public const int PeerEnterRsp = 0x0001_0003;
        }

    }


}