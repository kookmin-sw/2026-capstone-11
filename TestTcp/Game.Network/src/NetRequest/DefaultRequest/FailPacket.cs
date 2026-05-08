
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Game.Network.Service
{
    public class FailPacket
    {
        public static IPacketMeta<FailPacket> Meta = new FailPacketMeta();
        public static IPacketCodec<FailPacket> Codec = new FailPacketCodec();
        public enum FailType : int
        {
            Default = default,
            FailDeserialize,
            NoDispatchRegistery,
            WrongArgument,
            ServerFault,
            CustomMessage,
        }

        public static string GetMessage(FailType type)
        {
            switch (type)
            {
                case FailType.FailDeserialize: return "Message Deserialize Failed";
                case FailType.NoDispatchRegistery: return "NoDispatchRegistery";
                case FailType.WrongArgument: return "Argument is wrong";
                case FailType.ServerFault: return "Server Fail";
                default : return "Fail";
            }
        }

        public FailPacket(FailType t, string s)
        {
            type = t;
            msg = (type == FailType.CustomMessage)? s : GetMessage(type);
        }
        public FailPacket(FailType t)
        {
            type = t;
            msg = GetMessage(type);
        }

        public FailType type;
        public string msg;
    }

    public class FailPacketMeta : IPacketMeta<FailPacket>
    {
        public int Id => PacketId.Constant.FailRsp;
        public bool IsFixedSize => false;
    }

    public class FailPacketCodec : IPacketCodec<FailPacket>
    {
        public int GetSize(FailPacket data)
        {
            return 4 + 4 + Encoding.UTF8.GetByteCount(data.msg);
        }
        public void Write(ref PacketWriter writer, FailPacket data)
        {
            writer.WriteInt32((int)data.type);
            writer.WriteString(data.msg);
        }
        public FailPacket Read(ref PacketReader reader)
        {
            var t = (FailPacket.FailType)reader.ReadInt32();
            var s = reader.ReadString();

            return new FailPacket(t, s);
        }
    }
}