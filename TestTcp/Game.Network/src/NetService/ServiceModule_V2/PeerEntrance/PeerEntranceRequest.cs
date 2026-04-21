using System.Text;
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public class PeerEntranceRequestCodec : IPacketCodec<PeerEntranceRequest>
    {
        public int GetSize(PeerEntranceRequest value)
        {
            return ConnInfo.Codec.GetSize(value.Info);
        }

        public void Write(ref PacketWriter writer, PeerEntranceRequest value)
            => ConnInfo.Codec.Write(ref writer, value.Info);

        public PeerEntranceRequest Read(ref PacketReader reader) 
            => new PeerEntranceRequest(ConnInfo.Codec.Read(ref reader));
    }


    public class PeerEntranceRequest
    {
        public static PeerEntranceRequestCodec Codec = new();
        public readonly ConnInfo Info;
        public PeerEntranceRequest(ConnInfo info)
        {
            Info = info;
        }
    }


    public class PeerEntranceResponseCodec : IPacketCodec<PeerEntranceResponse>
    {
        public int GetSize(PeerEntranceResponse value)
        {
            return 4 
                    + 4 
                    + Encoding.UTF8.GetByteCount(value.Msg) 
                    + ConnInfo.Codec.GetSize(value.RemotePeerInfo); 
        }

        public void Write(ref PacketWriter writer, PeerEntranceResponse value)
        {
            writer.WriteInt32((int)value.result);
            writer.WriteString(value.Msg);
            ConnInfo.Codec.Write(ref writer, value.RemotePeerInfo);
        }
        public PeerEntranceResponse Read(ref PacketReader reader)
        {
            var result = (PeerEntranceResponse.Result) reader.ReadInt32();
            string msg = reader.ReadString();
            ConnInfo info = ConnInfo.Codec.Read(ref reader);
            return new PeerEntranceResponse(result, info, msg);
        }
    };

    public class PeerEntranceResponse
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
        public PeerEntranceResponse(bool isSucc, ConnInfo connInfo, string msg = "")
        {
            result = (isSucc) ? Result.Succ : Result.Fail;
            Msg = msg;
            RemotePeerInfo = connInfo;
        }
        public PeerEntranceResponse(Result r, ConnInfo connInfo, string msg = "")
        {
            result = r;
            Msg= msg;
            RemotePeerInfo = connInfo;
        }

        public bool IsSucc => result == Result.Succ;
    }
    

}
