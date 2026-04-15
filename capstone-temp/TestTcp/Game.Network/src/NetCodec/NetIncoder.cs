
using System.Buffers.Binary;
using System.Runtime.CompilerServices;
using System.Text;

namespace Game.Network
{
    // public readonly struct Codec
    // {
    //     // header
    //     public uint flag { get; }
    //     public int handlerNum { get; }
    //     public int queryNum { get; }
    //     public int reserved { get; }

    //     // body
    //     public byte[] data { get; }
    // };


    public readonly struct Codec
    {
        public const int HeaderSize = 16;

        // header
        public uint Flag { get; }
        public int HandlerNum { get; }
        public int QueryNum { get; }
        public int Reserved { get; }

        // body
        public byte[] Data { get; }

        // Packet Flag Bit
        private static class FlagBit
        {
            public const uint None = 0x0000_0000;
            public const uint Control = 0x0000_0001;
            public const uint Respond = 0x0000_0001 << 1;
            public const uint Query = 0x0000_0001 << 2;
            public const uint Crypto = 0x0000_0001 << 3;
        }

        public Codec(uint flag, int handlerNum, int queryNum, int reaserved, byte[] data)
        {
            Flag = flag;
            HandlerNum = handlerNum;
            QueryNum = queryNum;
            Reserved = reaserved;
            Data = (data == null)? Array.Empty<byte>() : data;
        }

        public static Codec CreateMessage(int handlerNum, byte[] data,
                                            int reaserved = 0, bool isControl = false)
        {
            uint flag = FlagBit.None;
            if (isControl) flag |= FlagBit.Control;

            return new Codec(
                flag,
                handlerNum,
                0,
                reaserved,
                data
            );
        }

        public static Codec CreateQuery(int handlerNum, int queryNum, byte[] data,
                                            int reaserved = 0, bool isControl = false)
        {
            uint flag = FlagBit.Query;
            if (isControl) flag |= FlagBit.Control;

            return new Codec(
                flag,
                handlerNum,
                queryNum,
                reaserved,
                data
            );
        }

        public static Codec CreateRespond(int handlerNum, int queryNum, byte[] data,
                                            int reaserved = 0, bool isControl = false)
        {
            uint flag = FlagBit.Respond;
            if (isControl) flag |= FlagBit.Control;

            return new Codec(
                flag,
                handlerNum,
                queryNum,
                reaserved,
                data
            );
        }

        public static Codec CreateEmpty()
        {
            return new Codec (
                FlagBit.None,
                0,
                0,
                0,
                Array.Empty<byte>()
            );
        }

        public bool IsPacketValid()
        {
            bool respond = IsRespond();
            bool query = IsQuery();
            
            return  !(respond && query) // Can't be Respond & Query 
                    //&& (QueryNum == 0 ^ (respond || query)) // Respond or Query but No queryNum. Message has QueryNum
                ;
        }

        public bool IsControl() => (Flag & FlagBit.Control) != 0;

        public bool IsRespond() => (Flag & FlagBit.Respond) != 0;

        public bool IsQuery() => (Flag & FlagBit.Query) != 0;

        
    };


    public class NetCodec
    {
        public const int HeaderSize = 16;

        public static byte[] EncodeWithHeader(Codec c)
        {
            var data = (c.Data == null) ? Array.Empty<byte>() : c.Data;

            int size = HeaderSize + data.Length;

            byte[] packet = new byte[size];

            BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(0, 4), c.Flag);
            BinaryPrimitives.WriteInt32LittleEndian(packet.AsSpan(4, 4), c.HandlerNum);
            BinaryPrimitives.WriteInt32LittleEndian(packet.AsSpan(8, 4), c.QueryNum);
            BinaryPrimitives.WriteInt32LittleEndian(packet.AsSpan(12, 4), c.Reserved);

            data.AsSpan().CopyTo(packet.AsSpan(HeaderSize));

            return packet;
        }
        
        public static Codec DecodeWithHeader(byte[] packet)
        {
            if (packet == null || packet.Length < HeaderSize)
                return Codec.CreateMessage(0, Array.Empty<byte>());

            uint flag      = BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(0,4));
            int handlerNum = BinaryPrimitives.ReadInt32LittleEndian(packet.AsSpan(4, 4));
            int queryNum   = BinaryPrimitives.ReadInt32LittleEndian(packet.AsSpan(8, 4));
            int reserved   = BinaryPrimitives.ReadInt32LittleEndian(packet.AsSpan(12, 4));


            byte[] data;
            if (packet.Length == HeaderSize) data = Array.Empty<byte>();
            else data = packet.AsSpan(HeaderSize).ToArray();

            return new Codec (flag, handlerNum, queryNum, reserved, data);
        }
    }
}