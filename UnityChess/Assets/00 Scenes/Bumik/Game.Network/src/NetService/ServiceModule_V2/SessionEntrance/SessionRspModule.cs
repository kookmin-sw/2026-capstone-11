

using System;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Game.Network.Service
{
    public class SessionRspModule : IServiceModule, INetEventHandler
                                    , IRequestHandler<SessionReq, SessionRsp>
    {
        public int HandlerId => NetEventHandlerId.Constant.Session;
        private INetAPI _net;
        private IPeerDictSessionWriter _other;
        private IGameWriter _game;
        private IRouteWriter _router;

        public void Init(ServiceContext_V2 context)
        {
            _net = context.Net;
            _other = context.Other;
            _game = context.Games;
            _router = context.Router;


            _net.SetReceiveHandler(this);
        }

        public SessionRsp Handle(ConnId connId, SessionReq req)
        {
            switch (req.type)
            {
                case SessionReqType.ReqEnter:
                    return HandleEnterReq(connId, req);

                case SessionReqType.ReqExit:
                    return HandleExitReq(connId, req);

                default:
                    return new SessionRsp(SessionRspType.Error, "Wrong Req");
            }
        }

        public void OnQuery(ConnId connId, int queryNum, byte[] raw)
        {
            PacketReader reader = new(raw);
            try
            {
                SessionReq req = SessionReq.Codec.Read(ref reader);

                var rsp = Handle(connId, req);

                var payload = new byte[SessionRsp.Codec.GetSize(rsp)];
                PacketWriter writer = new(payload);
                SessionRsp.Codec.Write(ref writer, rsp);

                _net.Send(HandlerId, queryNum, connId, payload);
            }

            catch (Exception e)
            {
                Log.WriteLog($"Exception on reading session req from {connId}. Exception: {e.Message}");
            }
        }

        private SessionRsp HandleEnterReq(ConnId connId, SessionReq req)
        {
            if (!_other.TryGetSession(connId, out var info))
                return new SessionRsp(SessionRspType.Failed, "Fail to Load SessionInfo");

            if (info.state != SessionInfo.State.Entering)
                return new SessionRsp(SessionRspType.Failed, "Wrong Req. Peer is Not Entering");

            if (!_game.IsSessionActive(info.id) && !_game.TryCreateSession(info.id))
                return new SessionRsp(SessionRspType.Failed, "Fail to Create New Session");
            
            var playerId = SessionPlayerId.NewId();
            if (!_game.TryEnterPlayer(info.id, playerId))
                return new SessionRsp(SessionRspType.Failed, "Fail to Enter Session");

            info.Enter(playerId);
            _router.AddRoute(info.id, info.playerId, connId);
            return new SessionRsp(SessionRspType.Accepted, info.id, info.playerId, "Accept to Session. Rsp with SessionPlayerId");
        }

        private SessionRsp HandleExitReq(ConnId connId, SessionReq req)
        {
            if (!_other.TryGetSession(connId, out var info))
                return new SessionRsp(SessionRspType.Failed, "Fail to Load SessionInfo");

            if (info.state != SessionInfo.State.Entered)
                return new SessionRsp(SessionRspType.Failed, "Wrong Req. Peer is Not Entered");

            if (!_game.TryExitPlayer(info.id, info.playerId))
                return new SessionRsp(SessionRspType.Failed, "Fail to Exit Session");

            info.Exit();
            _router.RemoveRoute(info.id, info.playerId, out ConnId id);
            return new SessionRsp(SessionRspType.Accepted, "Accept Exit from Session. Rsp with Default");
        }

    }
}