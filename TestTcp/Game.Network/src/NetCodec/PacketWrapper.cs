
using System;
using System.ComponentModel;
using System.Data.Common;
using System.Threading;

namespace Game.Network.Service
{
    public class PacketWrapper
    {
        private byte[] _packet = Array.Empty<byte>();
        public byte[] Raw => _packet;
        
        public PacketWrapper(byte[] packet)
        {
            _packet = packet;
        }
        public static PacketWrapper MakeWrap<T>(T packet, IPacketMeta<T> meta, IPacketCodec<T> codec)
        {
            var wrapper = new PacketWrapper(new byte[ codec.GetSize(packet) + 4]);
            PacketWriter writer = new(wrapper._packet);
            writer.WriteInt32(meta.Id);
            codec.Write(ref writer, packet);
            return wrapper;
        }

        public static PacketWrapper Empty => new(Array.Empty<byte>());

        public int ReadId()
        {
            PacketReader reader = new (_packet);
            if (reader.Remain < 4) return PacketId.Constant.FailRsp;
            else return reader.ReadInt32();
        }

        public T? Unwrap<T>(IPacketMeta<T> meta, IPacketCodec<T> codec)
        {
            try
            {
                PacketReader reader = new(_packet);
                if (reader.ReadInt32() != meta.Id) return default(T); 

                return codec.Read(ref reader);
            }
            catch
            {
                return default(T);
            }
        } 
    }
}