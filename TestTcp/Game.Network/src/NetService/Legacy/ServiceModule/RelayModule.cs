
using System.Buffers;
using System.Buffers.Binary;
using System.Data.Common;
using System.Drawing;
using Game.Network.Protocol;

// namespace Game.Network
// {
//     public class RelayModule : ServiceModule, INetReceiveEventHandler
//     {
//         public int HandlerId => NetEventHandlerId.Constant.Relay;
        
//         public void OnReceive(string ConnId, byte[] raw)
//         {
            
//         }

//         public static byte[] AttachRelayHeader(SessionPlayerId playerId, byte[] raw)
//         {
//             byte[] buffer = new byte[raw.Length + SessionPlayerId.StaticSize];

//             BinaryPrimitives.WriteInt32LittleEndian(buffer.AsSpan(0, 4), playerId.Value);
//             Buffer.BlockCopy(raw, 0, buffer, SessionPlayerId.StaticSize, raw.Length);
//             return buffer;
//         }

//         public static byte[] ReadRelayPayload(byte[] raw)
//         {
//             return raw.AsSpan(SessionPlayerId.StaticSize, raw.Length).ToArray();
//         }

//         public static SessionPlayerId ReadRelayHeader(byte[] raw)
//         {
//             int v = BinaryPrimitives.ReadInt32LittleEndian(raw.AsSpan(0, 4));
//             return new SessionPlayerId(v);
//         }


//     }
// }