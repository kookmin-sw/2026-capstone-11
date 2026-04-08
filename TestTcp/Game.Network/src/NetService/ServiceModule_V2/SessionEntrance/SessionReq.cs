namespace Game.Network.Service
{
    public enum SessionReqType : int
    {
        ReqEnter,
        ReqExit,
    }

    public class SessionReq
    {
        public static SessionReqCodec Codec = new();

        public SessionReqType type;
        public SessionId sessionId;
        public SessionPlayerId playerId;

        public SessionReq(SessionReqType Type, SessionId SessionId, SessionPlayerId PlayerId)
        {
            type = Type;
            sessionId = SessionId;
            playerId = PlayerId;
        }
        public SessionReq(SessionReqType Type, SessionId SessionId)
        {
            type = Type;
            sessionId = SessionId;
            playerId = SessionPlayerId.Default;
        }
        public SessionReq(SessionReqType Type)
        {
            type = Type;
            sessionId = SessionId.Default;
            playerId = SessionPlayerId.Default;
        }

    }

    public class SessionReqCodec : IPacketCodec<SessionReq>
    {
        public int GetSize(SessionReq value) 
            => 4 + SessionId.StaticSize + SessionPlayerId.StaticSize;
        
        public void Write(ref PacketWriter writer, SessionReq value)
        {
            writer.WriteInt32((int)value.type);
            writer.WriteInt32(value.sessionId.Value);
            writer.WriteInt32(value.playerId.Value);
        }

        public SessionReq Read(ref PacketReader reader)
        {
            var Type = (SessionReqType) reader.ReadInt32();
            var Id = new SessionId(reader.ReadInt32());
            var PlayerId = new SessionPlayerId(reader.ReadInt32());

            return new SessionReq(Type, Id, PlayerId);
        }

    }


}