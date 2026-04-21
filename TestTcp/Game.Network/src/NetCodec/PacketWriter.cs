
using System.Buffers.Binary;
using System.Text;

namespace Game.Network
{
    public ref struct PacketWriter
    {
        private Span<byte> _buffer;
        private int _offset;

        public PacketWriter(Span<byte> buffer)
        {
            _buffer = buffer;
            _offset = 0;
        }

        public Span<byte> Buffer => _buffer;
        public int Offset => _offset;

        public void WriteInt32(int data)
        {
            if (_buffer.Length - _offset < 4) throw new  InvalidOperationException("Not enough space.");
            BinaryPrimitives.WriteInt32LittleEndian(_buffer.Slice(_offset, 4), data);
            _offset += 4;
        }

        public void WriteInt16(short data)
        {
            if (_buffer.Length - _offset < 2) throw new  InvalidOperationException("Not enough space.");
            BinaryPrimitives.WriteInt16LittleEndian(_buffer.Slice(_offset, 2), data);
            _offset += 2;
        }

        public void WriteByte(byte data)
        {
            if (_buffer.Length - _offset < 1) throw new InvalidOperationException("Not enough space.");
            _buffer[_offset] = data;
            _offset += 1;
        }

        public void WriteBytes(ReadOnlySpan<byte> data)
        {
            if (_buffer.Length - _offset < data.Length) throw new InvalidOperationException("Not enough space.");
            data.CopyTo(_buffer.Slice(_offset));
            _offset += data.Length;
        }

        public void WriteString(string data)
        {
            if (data == null || data == String.Empty)
            {
                WriteInt32(0);    
                return;
            }

            int length = Encoding.UTF8.GetByteCount(data);
            if (_buffer.Length - _offset < length + 4) throw new InvalidOperationException("Not enough space.");
            WriteInt32(length);
            Encoding.UTF8.GetBytes(data, _buffer.Slice(_offset));
            _offset += length;
        }
    }
}