using System.Text;
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public class PeerEnterReqCodec : IPacketCodec<PeerEnterReq>
    {
        public int GetSize(PeerEnterReq value)
        {
            return ConnInfo.Codec.GetSize(value.Info);
        }

        public void Write(ref PacketWriter writer, PeerEnterReq value)
            => ConnInfo.Codec.Write(ref writer, value.Info);

        public PeerEnterReq Read(ref PacketReader reader)
            => new PeerEnterReq(ConnInfo.Codec.Read(ref reader));
    }

    public class PeerEnterReqMeta : IPacketMeta<PeerEnterReq>
    {
        public int Id => PacketId.Constant.PeerEnterReq;
    }


    public class PeerEnterReq
    {
        public static IPacketCodec<PeerEnterReq> Codec = new PeerEnterReqCodec();
        public static IPacketMeta<PeerEnterReq> Meta = new PeerEnterReqMeta();

        public readonly ConnInfo Info;
        public PeerEnterReq(ConnInfo info)
        {
            Info = info;
        }
    }

    public class PeerEnterRsp
    {
        public static IPacketCodec<PeerEnterRsp> Codec = new PeerEnterRspCodec();
        public static IPacketMeta<PeerEnterRsp> Meta = new PeerEnterRspMeta();

        public ConnInfo RemotePeerInfo;
        public PeerEnterRsp(ConnInfo connInfo)
        {
            RemotePeerInfo = connInfo;
        }
    }

    public class PeerEnterRspMeta : IPacketMeta<PeerEnterRsp>
    {
        public int Id => PacketId.Constant.PeerEnterRsp;
    }

    public class PeerEnterRspCodec : IPacketCodec<PeerEnterRsp>
    {
        public int GetSize(PeerEnterRsp value)
        {
            return ConnInfo.Codec.GetSize(value.RemotePeerInfo);
        }

        public void Write(ref PacketWriter writer, PeerEnterRsp value)
        {
            ConnInfo.Codec.Write(ref writer, value.RemotePeerInfo);
        }
        public PeerEnterRsp Read(ref PacketReader reader)
        {
            return new PeerEnterRsp(ConnInfo.Codec.Read(ref reader));
        }
    };

}
