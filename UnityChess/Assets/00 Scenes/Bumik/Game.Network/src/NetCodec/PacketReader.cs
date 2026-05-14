
using System;
using System.Buffers.Binary;
using System.Text;

namespace Game.Network
{
    public ref struct PacketReader
    {
        private ReadOnlySpan<byte> _buffer;
        private int _offset;

        public PacketReader(ReadOnlySpan<byte> buffer)
        {
            _buffer = buffer;
            _offset = 0;
        }

        public int Remain => _buffer.Length - _offset;
        public int Offset => _offset;

        public int ReadInt32()
        {
            if (Remain < 4) throw new InvalidOperationException("not enough space");
            int value = BinaryPrimitives.ReadInt32LittleEndian(_buffer.Slice(_offset, 4));
            _offset += 4;
            return value;
        }

        public short ReadInt16()
        {
            if (Remain < 2) throw new InvalidOperationException("not enough space");
            short value = BinaryPrimitives.ReadInt16LittleEndian(_buffer.Slice(_offset, 2));
            _offset += 2;
            return value;
        }

        public byte ReadByte()
        {
            if (Remain < 1) throw new InvalidOperationException("not enough space");
            byte value = _buffer[_offset];
            _offset++;
            return value;
        }

        public ReadOnlySpan<byte> ReadBytes(int length)
        {
            if (Remain < length) throw new InvalidOperationException("not enough space");
            ReadOnlySpan<byte> data = _buffer.Slice(_offset, length);
            _offset += length;
            return data;
        }

        public string ReadString()
        {
            int length = ReadInt32();
            if (Remain < length) throw new InvalidOperationException("not enough space");
            string data = Encoding.UTF8.GetString(_buffer.Slice(_offset, length));
            _offset += length;
            return data;
        }
    }
}