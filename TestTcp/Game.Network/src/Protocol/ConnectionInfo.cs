
using System.Buffers.Binary;
using System.Drawing;
using System.Linq.Expressions;
using System.Runtime.InteropServices;
using System.Text;

namespace Game.Network.Protocol
{
    public class ConnectionInfo
    {
        // Network 식별용
        public readonly NetworkType networkType;
        public readonly ConnectionType connectionType;
        public readonly int sessionId;
        public readonly int accountId;


        // payload: int accountNameSize;
        // payload: int appVersionSize;
        // payload: int tokenSize;

        public readonly string accountName;
        public readonly string appVersion;
        public readonly string token;


        public const int StaticSize = sizeof(int) * 7;

        public ConnectionInfo(
            NetworkType netType,
            ConnectionType connType,
            int seesion_id,
            int account_id,
            string account_name,
            string app_version,
            string Token
        )
        {
            networkType = netType;
            connectionType = connType;
            sessionId = seesion_id;
            accountId = account_id;
            accountName = account_name;
            appVersion = app_version;
            token = Token;
        }

        public static byte[] Serialize(ConnectionInfo info)
        {
            int accountNameSize = Encoding.UTF8.GetByteCount(info.accountName);
            int appVersionSize = Encoding.UTF8.GetByteCount(info.appVersion);
            int tokenSize = Encoding.UTF8.GetByteCount(info.token);

            byte[] payload = new byte[StaticSize
                                        + accountNameSize
                                        + appVersionSize
                                        + tokenSize];


            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(0, 4), (int)info.networkType);
            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(4, 4), (int)info.connectionType);
            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(8, 4), info.sessionId);
            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(12, 4), info.accountId);

            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(16, 4), accountNameSize);
            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(20, 4), appVersionSize);
            BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(24, 4), tokenSize);

            int offset = StaticSize;
            Encoding.UTF8.GetBytes(info.accountName, payload.AsSpan(offset, accountNameSize));

            offset += accountNameSize;
            Encoding.UTF8.GetBytes(info.appVersion, payload.AsSpan(offset, appVersionSize));

            offset += appVersionSize;
            Encoding.UTF8.GetBytes(info.token, payload.AsSpan(offset, tokenSize));

            return payload;
        }

        /// <summary>
        /// raw에서 사이즈 이상시 null<byte> 반환
        /// </summary>
        /// <param name="raw"></param>
        /// <returns></returns>
        public static ConnectionInfo? Deserialize(byte[] raw)
        {
            if (raw.Length < StaticSize) return null;    
        
            NetworkType nt = (NetworkType)BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(0, 4));
            ConnectionType ct = (ConnectionType)BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(4, 4));
            int session_id = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(8, 4));
            int account_id = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(12, 4));
            int accountNameSize = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(16, 4));
            int appVersionSize = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(20, 4));
            int tokenSize = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(24, 4));

            if (accountNameSize < 0 || appVersionSize < 0 || tokenSize < 0) return null;
            if (StaticSize + accountNameSize + appVersionSize + tokenSize != raw.Length) return null;

            int offset = StaticSize;
            string account_name = Encoding.UTF8.GetString(raw.AsSpan(offset, accountNameSize));

            offset += accountNameSize;
            string app_version = Encoding.UTF8.GetString(raw.AsSpan(offset, appVersionSize));

            offset += appVersionSize;
            string token = Encoding.UTF8.GetString(raw.AsSpan(offset, tokenSize));

            return new ConnectionInfo(
                nt, 
                ct,
                session_id,
                account_id,
                account_name,
                app_version,
                token
            );
        }
    }


}

