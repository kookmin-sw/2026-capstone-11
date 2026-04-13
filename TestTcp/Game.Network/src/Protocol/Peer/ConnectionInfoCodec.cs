
using System.Text;

namespace Game.Network.Protocol
{
    public class ConnectionInfoCodec : IPacketCodec<ConnectionInfo>
    {
        public int GetSize(ConnectionInfo data)
        {
            return ConnectionInfo.StaticSize + data.playerPlayformSize + data.appVersionSize + data.tokenSize;
        }

        public void Write(ref PacketWriter writer, ConnectionInfo data)
        {
            writer.WriteInt32((int)(data.networkType));
            writer.WriteInt32((int)(data.connectionType));
            writer.WriteInt32(data.sessionId);
            writer.WriteInt32(data.accountId);
            writer.WriteInt32(data.playerPlayformSize);
            writer.WriteBytes(Encoding.UTF8.GetBytes(data.playerPlatformId));
            writer.WriteInt32(data.appVersionSize);
            writer.WriteBytes(Encoding.UTF8.GetBytes(data.appVersion));
            writer.WriteInt32(data.tokenSize);
            writer.WriteBytes(Encoding.UTF8.GetBytes(data.token));
        }

        public ConnectionInfo Read(ref PacketReader reader)
        {
            var netType = (NetworkType) reader.ReadInt32();
            var connType = (ConnectionType) reader.ReadInt32();
            var sessId = reader.ReadInt32();
            var accountId = reader.ReadInt32();
            var size = reader.ReadInt32();
            string playerPlatformId = Encoding.UTF8.GetString(reader.ReadBytes(size));
            size = reader.ReadInt32();
            string appVersion = Encoding.UTF8.GetString(reader.ReadBytes(size));
            size = reader.ReadInt32();
            string token = Encoding.UTF8.GetString(reader.ReadBytes(size));
        
            return new ConnectionInfo(
                netType,
                connType,
                sessId,
                accountId,
                playerPlatformId,
                appVersion,
                token
            );
        }
    }
}