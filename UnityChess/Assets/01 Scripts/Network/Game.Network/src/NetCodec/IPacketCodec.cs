
using System.Drawing;
using System.Net.WebSockets;

namespace Game.Network
{
    public interface IPacketCodec<T>
    {
        int GetSize(T data);
        void Write(ref PacketWriter writer, T data);
        T Read(ref PacketReader reader);
    }
}