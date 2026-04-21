
using System.Text;

namespace Game.Network.Service
{
    public class SimpleReq
    {
        public static SimpleReqCodec Codec = new();

        public string Msg;

        public SimpleReq(string msg = "")
        {
            Msg = msg ?? "";
        }
    }

    public class SimpleReqCodec : IPacketCodec<SimpleReq>
    {
        public int GetSize(SimpleReq value)
        {
            return 4
                    + Encoding.UTF8.GetByteCount(value.Msg);
        }

        public void Write(ref PacketWriter writer, SimpleReq value)
        {
            writer.WriteString(value.Msg);
        }

        public SimpleReq Read(ref PacketReader reader)
        {
            string msg = reader.ReadString();
            return new SimpleReq(msg);
        }
    };
}
