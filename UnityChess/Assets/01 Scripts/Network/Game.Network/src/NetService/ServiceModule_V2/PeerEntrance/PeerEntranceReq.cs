using System.Text;
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public class PeerEntranceRequestCodec : IPacketCodec<PeerEntranceReq>
    {
        public int GetSize(PeerEntranceReq value)
        {
            return ConnInfo.Codec.GetSize(value.Info);
        }

        public void Write(ref PacketWriter writer, PeerEntranceReq value)
            => ConnInfo.Codec.Write(ref writer, value.Info);

        public PeerEntranceReq Read(ref PacketReader reader) 
            => new PeerEntranceReq(ConnInfo.Codec.Read(ref reader));
    }


    public class PeerEntranceReq
    {
        public static PeerEntranceRequestCodec Codec = new();
        public readonly ConnInfo Info;
        public PeerEntranceReq(ConnInfo info)
        {
            Info = info;
        }
    }


    public class PeerEntranceResponseCodec : IPacketCodec<PeerEntranceRsp>
    {
        public int GetSize(PeerEntranceRsp value)
        {
            return 4 
                    + 4 
                    + Encoding.UTF8.GetByteCount(value.Msg) 
                    + ConnInfo.Codec.GetSize(value.RemotePeerInfo); 
        }

        public void Write(ref PacketWriter writer, PeerEntranceRsp value)
        {
            writer.WriteInt32((int)value.result);
            writer.WriteString(value.Msg);
            ConnInfo.Codec.Write(ref writer, value.RemotePeerInfo);
        }
        public PeerEntranceRsp Read(ref PacketReader reader)
        {
            var result = (PeerEntranceRsp.Result) reader.ReadInt32();
            string msg = reader.ReadString();
            ConnInfo info = ConnInfo.Codec.Read(ref reader);
            return new PeerEntranceRsp(result, info, msg);
        }
    };

    public class PeerEntranceRsp
    {
        public static PeerEntranceResponseCodec Codec = new();
        public enum Result : int
        {
            Fail,
            Succ 
        }

        public Result result;
        public string Msg;
        public ConnInfo RemotePeerInfo;
        public PeerEntranceRsp(bool isSucc, ConnInfo connInfo, string msg = "")
        {
            result = (isSucc) ? Result.Succ : Result.Fail;
            Msg = msg;
            RemotePeerInfo = connInfo;
        }
        public PeerEntranceRsp(Result r, ConnInfo connInfo, string msg = "")
        {
            result = r;
            Msg= msg;
            RemotePeerInfo = connInfo;
        }

        public bool IsSucc => result == Result.Succ;
    }
    

}
