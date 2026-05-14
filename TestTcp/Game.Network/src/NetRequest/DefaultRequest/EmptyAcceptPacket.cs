using System;

namespace Game.Network.Service
{
    public class EmptyAcceptPacket
    {
        public static IPacketMeta<EmptyAcceptPacket> Meta  = new EmptyAcceptPacketMeta();
        public static IPacketCodec<EmptyAcceptPacket> Codec = new EmptyAceeptPacketCodec();

        private const int MagicNum = 0x1302_1023;


        private class EmptyAcceptPacketMeta : IPacketMeta<EmptyAcceptPacket>
        {
            public int Id => PacketId.Constant.EmptyAcceptPacket;
        }

        private class EmptyAceeptPacketCodec : IPacketCodec<EmptyAcceptPacket>
        {
            public int GetSize(EmptyAcceptPacket data) => 4;

            public void Write(ref PacketWriter writer, EmptyAcceptPacket data)
            {
                writer.WriteInt32(MagicNum);
            }

            public EmptyAcceptPacket Read(ref PacketReader reader)
            {
                int magic = reader.ReadInt32();
                if (magic != MagicNum) throw new InvalidOperationException("Invalid magic number.");
                return new EmptyAcceptPacket();
            }
        }
    } 
}