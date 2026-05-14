using System.Diagnostics;
using System.Text;
using System.Xml;
using Game.Network.Protocol;

namespace Game.Network.Service
{
    public class ConnInfoCodec : IPacketCodec<ConnInfo>
    {
        public int GetSize(ConnInfo value)
        {
            return 4    // enum NetworkType 
                    + 4     // enum ConnectionType
                    + 12    // for string length
                    + Encoding.UTF8.GetByteCount(value.PlatformName)
                    + Encoding.UTF8.GetByteCount(value.AccountId)
                    + Encoding.UTF8.GetByteCount(value.AppVersion);
        }

        public int GetSize(IConnInfoReader value)
        {
            return 4    // enum NetworkType 
                    + 4     // enum ConnectionType
                    + 12    // for string length
                    + Encoding.UTF8.GetByteCount(value.PlatformName)
                    + Encoding.UTF8.GetByteCount(value.AccountId)
                    + Encoding.UTF8.GetByteCount(value.AppVersion);
        }
        
        public void Write(ref PacketWriter writer, ConnInfo value)
        {
            writer.WriteInt32((int)value.networkType);
            writer.WriteInt32((int)value.connectionType);
            writer.WriteString(value.PlatformName);
            writer.WriteString(value.AccountId);
            writer.WriteString(value.AppVersion);
        }

        public void Write(ref PacketWriter writer, IConnInfoReader value)
        {
            writer.WriteInt32((int)value.networkType);
            writer.WriteInt32((int)value.connectionType);
            writer.WriteString(value.PlatformName);
            writer.WriteString(value.AccountId);
            writer.WriteString(value.AppVersion);
        }

        public ConnInfo Read(ref PacketReader reader)
        {
            NetworkType networkType = (NetworkType)reader.ReadInt32();
            ConnectionType connType = (ConnectionType)reader.ReadInt32();
            string platformName = reader.ReadString();
            string accountId = reader.ReadString();
            string appversion = reader.ReadString();

            return new ConnInfo(networkType, connType, platformName, accountId, appversion);
        }
    }
}