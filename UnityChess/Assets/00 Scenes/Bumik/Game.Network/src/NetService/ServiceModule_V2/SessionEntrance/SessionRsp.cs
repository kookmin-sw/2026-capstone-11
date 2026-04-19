
using System;
using System.Text;

namespace Game.Network.Service
{
    public enum SessionRspType : int
    {
        Accepted,
        Failed,
        Error
    }

    public class SessionRsp
    {
        public static SessionRspCodec Codec = new();

        public SessionRspType type;
        public SessionId sessionId;
        public SessionPlayerId playerId;
        public string msg = "";
        
        public SessionRsp(SessionRspType Type, SessionId SessionId, SessionPlayerId PlayerId, string Msg = "")
        {
            type = Type;
            sessionId = SessionId;
            playerId = PlayerId;
            msg = Msg ?? String.Empty;
        }
        public SessionRsp(SessionRspType Type, SessionId SessionId, string Msg = "")
        {
            type = Type;
            sessionId = SessionId;
            playerId = SessionPlayerId.Default;
            msg = Msg ?? String.Empty;
        }
        public SessionRsp(SessionRspType Type, string Msg = "")
        {
            type = Type;
            sessionId = SessionId.Default;
            playerId = SessionPlayerId.Default;
            msg = Msg ?? String.Empty;
        }
    }

    public class SessionRspCodec : IPacketCodec<SessionRsp>
    {
        public int GetSize(SessionRsp value) 
            => 4 + SessionId.StaticSize + SessionPlayerId.StaticSize + 4 + Encoding.UTF8.GetByteCount(value.msg);
        
        public void Write(ref PacketWriter writer, SessionRsp value)
        {
            writer.WriteInt32((int)value.type);
            writer.WriteInt32(value.sessionId.Value);
            writer.WriteInt32(value.playerId.Value);
            writer.WriteString(value.msg);
        }

        public SessionRsp Read(ref PacketReader reader)
        {
            var Type = (SessionRspType) reader.ReadInt32();
            var Id = new SessionId(reader.ReadInt32());
            var PlayerId = new SessionPlayerId(reader.ReadInt32());
            var Msg = reader.ReadString(); 

            return new SessionRsp(Type, Id, PlayerId, Msg);
        }

    }

}