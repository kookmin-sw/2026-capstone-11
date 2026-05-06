
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Game.Network.Service
{
    public class FailRsp
    {
        public static IPacketMeta<FailRsp> Meta = new FailRspMeta();
        public static IPacketCodec<FailRsp> Codec = new FailRspCodec();
        public enum FailType : int
        {
            Default = default,
            FailDeserialize,
            NoDispatchRegistery,
            WrongRequestArgument,
            ServerFault,
            CustomMessage,
        }

        private static string GetMessage(FailType type)
        {
            switch (type)
            {
                case FailType.FailDeserialize: return "Message Deserialize Failed";
                case FailType.NoDispatchRegistery: return "NoDispatchRegistery";
                case FailType.WrongRequestArgument: return "Request Argument is wrong";
                case FailType.ServerFault: return "Server Fail";
                default : return "Fail";
            }
        }

        public FailRsp(FailType t, string s)
        {
            type = t;
            msg = (type == FailType.CustomMessage)? s : GetMessage(type);
        }
        public FailRsp(FailType t)
        {
            type = t;
            msg = GetMessage(type);
        }

        public FailType type;
        public string msg;
    }

    public class FailRspMeta : IPacketMeta<FailRsp>
    {
        public int Id => RequestId.Constant.FailRsp;
        public bool IsFixedSize => false;
    }

    public class FailRspCodec : IPacketCodec<FailRsp>
    {
        public int GetSize(FailRsp data)
        {
            return 4 + 4 + Encoding.UTF8.GetByteCount(data.msg);
        }
        public void Write(ref PacketWriter writer, FailRsp data)
        {
            writer.WriteInt32((int)data.type);
            writer.WriteString(data.msg);
        }
        public FailRsp Read(ref PacketReader reader)
        {
            var t = (FailRsp.FailType)reader.ReadInt32();
            var s = reader.ReadString();

            return new FailRsp(t, s);
        }
    }
}