
using System.Text;

namespace Game.Network.Service
{
    public class SimpleRsp
    {
        public static SimpleRspCodec Codec = new();

        public enum Result : int
        {
            Accepted,
            Denied
        }

        public Result result;
        public string Msg;

        public SimpleRsp(bool isAccept, string msg = "")
        {
            result = (isAccept) ? Result.Accepted : Result.Denied;
            Msg = msg ?? "";
        }
        public SimpleRsp(Result rs, string msg = "")
        {
            result = rs;
            Msg = msg ?? "";
        }

        public static SimpleRsp Accepted(string msg) => new SimpleRsp(Result.Accepted, msg);
        public static SimpleRsp Denied(string msg) => new SimpleRsp(Result.Denied, msg); 

        public bool IsAccepted => result == Result.Accepted;
    }

    public class SimpleRspCodec : IPacketCodec<SimpleRsp>
    {
        public int GetSize(SimpleRsp value)
        {
            return 4 
                    + 4 
                    + Encoding.UTF8.GetByteCount(value.Msg);  
        }

        public void Write(ref PacketWriter writer, SimpleRsp value)
        {
            writer.WriteInt32((int)value.result);
            writer.WriteString(value.Msg);
        }
        public SimpleRsp Read(ref PacketReader reader)
        {
            var result = (SimpleRsp.Result) reader.ReadInt32();
            string msg = reader.ReadString();
            return new SimpleRsp(result,  msg);
        }
    };
}